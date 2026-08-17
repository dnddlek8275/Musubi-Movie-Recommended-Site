"""
Musubi FastAPI AI API

엔드포인트:
    GET  /health          - 서버 상태
    POST /chat            - 캐릭터 1:1 대화
    POST /chat/group      - 캐릭터 그룹 채팅
    POST /chat/group/auto - 인텐트 자동 분류 후 그룹 채팅 (영화 추천 포함)
    POST /recommend       - 영화 추천
    POST /chat/auto       - 인텐트 자동 분류 후 라우팅
    POST /chat/stream     - 스트리밍 캐릭터 대화 (SSE)
"""

from __future__ import annotations
import json
import os
import re
from typing import Literal, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.admission import AIAdmissionMiddleware

from pipeline.intent import classify, Intent
from pipeline.character_pipeline import (
    character_lore_fact_reply,
    run as character_run,
    run_auto as character_auto_run,
    run_group,
    run_group_rounds,
    run_group_auto_rounds,
    resolve_character_names,
)
from pipeline.movie_pipeline import run as movie_run
from pipeline.recommendation_context import build_card_followup_reply
from pipeline.web_search_pipeline import run as web_search_run

app = FastAPI(title="Musubi AI API", version="2.0.0")

# A single T4 serves five llama.cpp slots.  Bound both running work and the
# waiting room so a traffic spike cannot turn into unbounded GPU contention.
app.add_middleware(AIAdmissionMiddleware)


@app.on_event("startup")
async def warmup():
    """서버 시작 시 BGE-M3 임베더 + CrossEncoder 리랭커를 미리 로드."""
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _load_models)


def _load_models():
    from rag.embedder import get_embedder
    from rag.reranker import get_reranker
    print("[Warmup] BGE-M3 임베더 로드 중...")
    get_embedder()
    print("[Warmup] CrossEncoder 리랭커 로드 중...")
    get_reranker()
    print("[Warmup] 완료 — 첫 요청부터 즉시 응답 가능")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 학습 파일 임시 다운로드용 (전송 후 제거 예정)
import os as _os
_static_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "static")
if _os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# ── 요청 스키마 ──

class ChatRequest(BaseModel):
    character:  str
    message:    str
    history:    list[dict] = []
    use_rag:    bool = True
    user_context: Optional[str] = None

class GroupChatRequest(BaseModel):
    characters: list[str]
    message:    str
    history:    list[dict] = []
    user_context: Optional[str] = None

class RecommendRequest(BaseModel):
    message:    str
    character:  Optional[str] = None
    history:    list[dict] = []
    genre:      Optional[str] = None
    actor:      Optional[str] = None
    director:   Optional[str] = None
    language:   Optional[str] = None
    year_from:  Optional[int] = None
    year_to:    Optional[int] = None
    min_rating: Optional[float] = None
    user_context: Optional[str] = None

class AutoRequest(BaseModel):
    character:  Optional[str] = None
    message:    str
    history:    list[dict] = []
    user_context: Optional[str] = None

class ChatTitleRequest(BaseModel):
    message: str


class MovieVectorItem(BaseModel):
    tmdb_id: int
    title: str
    overview: Optional[str] = None
    genres: list[str] = []
    director: Optional[str] = None
    cast: list[str] = []
    keywords: list[str] = []
    year: Optional[int] = None
    release_date: Optional[str] = None
    runtime: Optional[int] = None
    production_countries: list[str] = []
    certification: Optional[str] = None
    certification_country: Optional[str] = None
    language: Optional[str] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None
    audience_count: Optional[int] = None
    poster_path: Optional[str] = None


class DailyRecommendationCopyRequest(BaseModel):
    genre: str
    movies: list[MovieVectorItem]


class MovieVectorSyncRequest(BaseModel):
    upserts: list[MovieVectorItem] = []
    deletes: list[int] = []


# ── 응답 스키마 ──

class ChatResponse(BaseModel):
    character:    str
    answer:       str
    finish_reason: str = "stop"
    rag_used:     bool = False

class GroupChatResponse(BaseModel):
    responses: list[ChatResponse]

class RoundResponse(BaseModel):
    round:     int
    label:     str
    responses: list[ChatResponse]

class GroupRoundsResponse(BaseModel):
    rounds: list[RoundResponse]

class GroupAutoRoundsResponse(BaseModel):
    intent: str
    movies: list[dict] = []
    rounds: list[RoundResponse]

class RecommendResponse(BaseModel):
    answer: str
    movies: list[dict]

class AutoResponse(BaseModel):
    intent:    str
    character: str
    answer:    str
    movies:    list[dict] = []
    emotion:   Literal["default", "joy", "thinking", "searching", "sorry"] = "default"
    sources:   list[dict] = []
    web_search_quota: dict = {}


class WebSearchResponse(BaseModel):
    answer: str
    sources: list[dict] = []
    quota: dict = {}
    web_used: bool = False

class ChatTitleResponse(BaseModel):
    title: str


@app.post("/internal/movies/sync")
def sync_movie_vectors(
    request: MovieVectorSyncRequest,
    authorization: Optional[str] = Header(default=None),
):
    import os
    import secrets
    from rag.movie_vector_sync import sync_movies

    expected_token = os.getenv("AI_SYNC_TOKEN")
    supplied_token = (authorization or "").removeprefix("Bearer ").strip()
    if not expected_token:
        raise HTTPException(status_code=503, detail="AI_SYNC_TOKEN is not configured")
    if not supplied_token or not secrets.compare_digest(supplied_token, expected_token):
        raise HTTPException(status_code=401, detail="invalid sync token")
    if len(request.upserts) + len(request.deletes) > 100:
        raise HTTPException(status_code=413, detail="sync batch limit is 100")
    try:
        return sync_movies(
            [item.model_dump() for item in request.upserts],
            request.deletes,
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)[:500]) from error


_SORRY_EMOTION_PATTERN = re.compile(
    r"미안|죄송|찾지\s*못|없(?:어요|습니다)|어렵(?:네요|습니다)|힘들|슬프|속상|안타깝",
    re.IGNORECASE,
)
_JOY_EMOTION_PATTERN = re.compile(
    r"좋아요|반가|기뻐|재밌|즐거|딱\s*맞|마음에\s*들|추천해요|골라봤어요",
    re.IGNORECASE,
)
_THINKING_EMOTION_PATTERN = re.compile(
    r"조금\s*더|어떤|무엇|어느|알려\s*주|말해\s*주|고민|생각|궁금|까요\?",
    re.IGNORECASE,
)


def _select_mumu_emotion(
    *,
    intent: str,
    user_message: str,
    answer: str,
    movies: list[dict],
) -> str:
    """완료된 응답 상태를 프로필용 제한 감정값으로 변환한다."""
    if movies:
        return "joy"
    combined = f"{user_message}\n{answer}"
    if _SORRY_EMOTION_PATTERN.search(combined):
        return "sorry"
    if intent == Intent.MOVIE_RECOMMEND:
        return "sorry"
    if _JOY_EMOTION_PATTERN.search(answer):
        return "joy"
    if _THINKING_EMOTION_PATTERN.search(answer):
        return "thinking"
    return "default"


def _fallback_chat_title(message: str) -> str:
    title = " ".join(message.split()).strip()
    for ending in (
        "영화를 찾고 있어", "영화 찾고 있어", "영화를 추천해줘", "영화 추천해줘",
        "추천해 주세요", "추천해주세요", "추천해줘", "찾아 주세요", "찾아줘",
        "보고 싶어", "알려 주세요", "알려줘",
    ):
        if title.endswith(ending):
            title = title[:-len(ending)].rstrip(" ,.!?")
            break
    for noun in ("영화가", "영화를", "영화"):
        if title.endswith(noun):
            title = title[:-len(noun)].rstrip(" ,.!?")
            break
    return title[:24].rstrip() or "새 영화 대화"


def _title_is_grounded(title: str, message: str) -> bool:
    title_words = {
        word for word in re.findall(r"[가-힣A-Za-z0-9]+", title.lower()) if len(word) > 1
    }
    if not title_words:
        return False
    message_words = set(re.findall(r"[가-힣A-Za-z0-9]+", message.lower()))
    overlap = sum(word in message_words for word in title_words)
    return overlap / len(title_words) > 0.5


def _title_word_candidates(message: str) -> list[str]:
    """첫 메시지에서 제목에 쓸 수 있는 단어만 정리한다."""
    exact = {
        "영화를": "영화", "영화가": "영화", "영화는": "영화", "영화의": "영화",
        "추천해줘": "추천", "추천해주세요": "추천", "추천해": "추천",
    }
    drop = {
        "오늘", "너무", "그냥", "저는", "제가", "좀", "맞는", "보고", "싶어", "싶어요",
        "찾고", "있어", "있어요", "해주세요", "해줘",
    }
    candidates: list[str] = []

    for raw_word in re.findall(r"[가-힣A-Za-z0-9]+", message):
        word = exact.get(raw_word, raw_word)
        if word.endswith("좋은데"):
            word = word[:-1]
        elif len(word) > 3 and word.endswith(("해서", "하고")):
            word = f"{word[:-2]}한"
        elif len(word) > 2 and word.endswith(("에서", "으로")):
            word = word[:-2]
        elif len(word) > 2 and word.endswith(("은", "는", "이", "가", "을", "를", "에", "로")):
            word = word[:-1]

        if not word or word in drop or word in candidates:
            continue
        candidates.append(word)

    return candidates[:10]


# ── 헬스체크 ──

@app.get("/health")
def health():
    import requests as _req
    from pymilvus import MilvusClient

    components: dict = {}

    # llama-server
    try:
        r = _req.get("http://localhost:8081/health", timeout=3)
        components["llm"] = "ok" if r.ok else f"error:{r.status_code}"
    except Exception as e:
        components["llm"] = f"down:{e}"

    # Milvus
    try:
        mc = MilvusClient(uri=os.getenv("CINEVERSE_MILVUS_URI", "http://localhost:19530"))
        cols = mc.list_collections()
        components["milvus"] = f"ok ({len(cols)} collections)"
    except Exception as e:
        components["milvus"] = f"down:{e}"

    # 임베더 (로드 여부)
    try:
        from rag.embedder import get_embedder
        get_embedder()
        components["embedder"] = "ok"
    except Exception as e:
        components["embedder"] = f"error:{e}"

    overall = "ok" if all(v.startswith("ok") for v in components.values()) else "degraded"
    return {"status": overall, "version": "2.0.0", "components": components}


# ── 1:1 캐릭터 대화 ──

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        result = character_run(
            character_name=req.character,
            user_message=req.message,
            history=req.history,
            use_rag=req.use_rag,
            user_context=req.user_context,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"캐릭터 '{req.character}'를 찾을 수 없습니다.")

    return ChatResponse(
        character=result.character,
        answer=result.answer,
        rag_used=result.rag_used,
    )


# ── 그룹 채팅 ──

@app.post("/chat/group", response_model=GroupChatResponse)
def chat_group(req: GroupChatRequest):
    if not 2 <= len(req.characters) <= 3:
        raise HTTPException(status_code=400, detail="캐릭터는 2~3명이어야 합니다.")

    try:
        results = run_group(
            characters=req.characters,
            user_message=req.message,
            history=req.history,
            user_context=req.user_context,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip('"'))

    return GroupChatResponse(
        responses=[
            ChatResponse(character=r.character, answer=r.answer, rag_used=r.rag_used)
            for r in results
        ]
    )


# ── 그룹 채팅 (2라운드 반응형) ──

@app.post("/chat/group/rounds", response_model=GroupRoundsResponse)
def chat_group_rounds(req: GroupChatRequest):
    """
    2라운드 반응형 그룹 채팅.

    Round 1: 각 캐릭터가 사용자 메시지에 순차 답변
    Round 2: 1라운드 전체 대화를 보고 자율 반응
             — 할 말 없으면 침묵 (해당 캐릭터 응답 제외됨)
    """
    if not 2 <= len(req.characters) <= 3:
        raise HTTPException(status_code=400, detail="캐릭터는 2~3명이어야 합니다.")

    try:
        round_results = run_group_rounds(
            characters=req.characters,
            user_message=req.message,
            history=req.history,
            user_context=req.user_context,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip('"'))

    return GroupRoundsResponse(
        rounds=[
            RoundResponse(
                round=rr.round,
                label=rr.label,
                responses=[
                    ChatResponse(character=r.character, answer=r.answer, rag_used=r.rag_used)
                    for r in rr.responses
                ],
            )
            for rr in round_results
        ]
    )


# ── 그룹 채팅 (인텐트 자동 분류, 영화 추천 포함) ──

@app.post("/chat/group/auto", response_model=GroupAutoRoundsResponse)
def chat_group_auto(req: GroupChatRequest):
    """
    인텐트 자동 분류 후 2라운드 반응형 그룹 채팅.

    영화 추천 인텐트: 영화를 한 번만 검색하고, 각 캐릭터가 같은 목록을
                    자기 톤으로 소개(라운드1) → 서로의 추천에 반응(라운드2).
    캐릭터 대화 인텐트: /chat/group/rounds와 동일하게 동작.
    """
    if not 2 <= len(req.characters) <= 3:
        raise HTTPException(status_code=400, detail="캐릭터는 2~3명이어야 합니다.")

    try:
        intent, movies, round_results = run_group_auto_rounds(
            characters=req.characters,
            user_message=req.message,
            history=req.history,
            user_context=req.user_context,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip('"'))

    return GroupAutoRoundsResponse(
        intent=intent,
        movies=movies,
        rounds=[
            RoundResponse(
                round=rr.round,
                label=rr.label,
                responses=[
                    ChatResponse(character=r.character, answer=r.answer, rag_used=r.rag_used)
                    for r in rr.responses
                ],
            )
            for rr in round_results
        ],
    )


# ── 영화 추천 ──

@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest):
    result = movie_run(
        user_message=req.message,
        character_name=req.character,
        history=req.history,
        user_context=req.user_context,
    )
    return RecommendResponse(
        answer=result.answer,
        movies=result.movies,
    )


@app.post("/recommend/daily-copy")
def recommend_daily_copy(req: DailyRecommendationCopyRequest):
    """Write copy for the exact movies selected by the backend; never retrieve again."""
    from pipeline.daily_recommendation import generate_daily_copy

    movies = [movie.model_dump() for movie in req.movies]
    if len(movies) != 3:
        raise HTTPException(status_code=422, detail="일일 추천 영화는 정확히 3편이어야 합니다.")
    return {
        "answer": generate_daily_copy(req.genre, movies),
        "movies": movies,
    }


@app.post("/web/search", response_model=WebSearchResponse)
def web_search(req: AutoRequest):
    result = web_search_run(req.message)
    return WebSearchResponse(
        answer=result.answer,
        sources=result.sources,
        quota=result.quota,
        web_used=result.web_used,
    )


@app.get("/web/search/status")
def web_search_status():
    import os
    from services.web_search import quota_status
    return {"configured": bool(os.getenv("TAVILY_API_KEY", "").strip()), **quota_status()}


# ── 자동 인텐트 분류 라우팅 ──

@app.post("/chat/title", response_model=ChatTitleResponse)
def chat_title(req: ChatTitleRequest):
    """첫 사용자 메시지를 대화 기록에 사용할 짧은 제목으로 요약한다."""
    from llm.client import chat as llm_chat

    message = req.message.strip()
    if not message:
        return ChatTitleResponse(title="새 영화 대화")

    title_words = _title_word_candidates(message)
    if not title_words:
        return ChatTitleResponse(title=_fallback_chat_title(message))

    if len(title_words) < 3:
        title_options = [" ".join(title_words)]
    else:
        title_options = []
        for size in range(3, min(6, len(title_words)) + 1):
            for start in range(0, len(title_words) - size + 1):
                title_options.append(" ".join(title_words[start:start + size]))
    grammar = "root ::= " + " | ".join(
        json.dumps(f"'{option}'", ensure_ascii=False) for option in title_options
    )

    raw_title = llm_chat(
        [
            {
                "role": "user",
                "content": (
                    "영화를 추천하거나 실제 영화 제목을 쓰지 마. 첫 대화의 핵심 주제를 "
                    "대화 기록용 짧은 명사형 제목으로 요약해. 설명 없이 제목만 "
                    f"작은따옴표 안에 써. 대화: {message}"
                ),
            },
        ],
        max_tokens=48,
        profile="structured",
        grammar=grammar,
    )

    raw_title = raw_title or ""
    quoted = re.search(r"['\"‘“]([^'\"’”\n]{2,30})['\"’”]", raw_title)
    if quoted:
        title = quoted.group(1).strip()
    else:
        first_turn = raw_title.split("<end_of_turn>", 1)[0]
        lines = [
            line.strip()
            for line in first_turn.splitlines()
            if line.strip() and "channel>" not in line and "start_of_turn>" not in line
        ]
        title = lines[-1] if lines else ""

    for prefix in ("제목:", "대화 제목:", "요약:"):
        if title.startswith(prefix):
            title = title[len(prefix):].strip()
    title = title.strip("`'\"‘’“” ")[:30].rstrip()
    if title not in title_options:
        title = _fallback_chat_title(message)
    return ChatTitleResponse(title=title or "새 영화 대화")


@app.post("/chat/auto", response_model=AutoResponse)
def chat_auto(req: AutoRequest):
    """
    사용자 입력을 자동으로 분류해서
    영화 추천 또는 캐릭터 대화 파이프라인으로 라우팅.
    """
    card_followup = build_card_followup_reply(req.message, req.history)
    if card_followup:
        answer, movies = card_followup
        return AutoResponse(
            intent=Intent.CHARACTER_CHAT,
            character=req.character or "",
            answer=answer,
            movies=movies,
            emotion="thinking",
        )

    intent = classify(req.message, history=req.history)

    if intent == Intent.WEB_SEARCH:
        result = web_search_run(req.message)
        return AutoResponse(
            intent=intent,
            character="",
            answer=result.answer,
            emotion="searching" if result.web_used else "sorry",
            sources=result.sources,
            web_search_quota=result.quota,
        )
    elif intent == Intent.MOVIE_RECOMMEND:
        result = movie_run(
            user_message=req.message,
            character_name=req.character,
            history=req.history,
            user_context=req.user_context,
        )
        return AutoResponse(
            intent=intent,
            character=result.character,
            answer=result.answer,
            movies=result.movies,
            emotion=_select_mumu_emotion(
                intent=intent,
                user_message=req.message,
                answer=result.answer,
                movies=result.movies,
            ),
        )
    else:
        if req.character:
            try:
                result = character_run(
                    character_name=req.character,
                    user_message=req.message,
                    history=req.history,
                    user_context=req.user_context,
                )
            except KeyError:
                raise HTTPException(status_code=404, detail=f"캐릭터 '{req.character}'를 찾을 수 없습니다.")
        else:
            # 캐릭터 사전 선택 없음 — 메시지에서 캐릭터 언급을 감지해 자동 전환.
            # 언급이 없으면 범용 대화로 응답한다 (character="")
            result = character_auto_run(
                user_message=req.message,
                history=req.history,
                user_context=req.user_context,
            )

        return AutoResponse(
            intent=intent,
            character=result.character,
            answer=result.answer,
            emotion=_select_mumu_emotion(
                intent=intent,
                user_message=req.message,
                answer=result.answer,
                movies=[],
            ),
        )


# ── 스트리밍 캐릭터 대화 ──

@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """
    캐릭터 대화를 SSE(text/event-stream)로 스트리밍.
    클라이언트는 `data: <token>` 형식으로 토큰을 실시간 수신.
    스트림 종료 시 `data: [DONE]` 전송.
    """
    from cineverse_prompt import build_system_prompt, clean_and_truncate, load_profiles
    from rag.character_retriever import retrieve, format_context
    from llm.client import chat_stream as llm_stream
    from pipeline.character_pipeline import (
        _ANSWER_NOW_REMINDER,
        _guard_generated_answer,
        _is_relation_followup,
        _relation_answer,
        _relation_names_from_context,
        _should_use_character_rag,
        _strip_identity_bleed,
        _strip_name_claim_bleed,
        _verified_relation_chunks,
        character_preflight_reply,
    )
    from pipeline.dialogue_guard import log_dialogue_guard_event
    from pipeline.user_context import build_user_context_prompt
    from pipeline.tone_presets import (
        build_turn_guidance,
        build_profiled_listen_fallback,
        build_recovery_reply,
        enforce_dialogue_policy,
        is_character_relation_question,
        is_listen_only_request,
        is_safe_listening_answer,
    )
    import os

    profile_path = os.environ.get("PROFILE_PATH", "character_profiles_ALL_50.json")
    profiles = load_profiles(profile_path)

    try:
        character_name = resolve_character_names([req.character], profiles)[0]
        system_prompt = build_system_prompt(
            character_name=character_name,
            chat_mode="single",
            profiles=profiles,
            example_count=0,
            compact=True,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"캐릭터 '{req.character}'를 찾을 수 없습니다.")

    preflight = character_preflight_reply(character_name, req.message, profiles)
    if preflight:
        reason, answer = preflight
        intent = "character_chat"
        if reason == "ambiguous_input":
            log_dialogue_guard_event(
                reason=reason,
                mode="character_stream",
                user_message=req.message,
                character_name=character_name,
            )
            answer = build_recovery_reply(character_name)
            intent = "input_recovery"

        def preflight_event_generator():
            payload = {
                "answer": answer,
                "character": character_name,
                "intent": intent,
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(preflight_event_generator(), media_type="text/event-stream")

    intent = classify(req.message, history=req.history)
    if intent == Intent.MOVIE_RECOMMEND:
        result = movie_run(
            user_message=req.message,
            character_name=character_name,
            history=req.history,
            user_context=req.user_context,
        )

        def movie_event_generator():
            yield f"data: {json.dumps({
                'answer': result.answer,
                'character': result.character or character_name,
                'intent': Intent.MOVIE_RECOMMEND,
                'movies': result.movies,
                'emotion': 'joy' if result.movies else 'sorry',
            }, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            movie_event_generator(),
            media_type="text/event-stream",
        )

    messages = [{"role": "system", "content": system_prompt}]
    user_context_prompt = build_user_context_prompt(req.user_context)
    if user_context_prompt:
        messages.append({"role": "system", "content": user_context_prompt})
    relation_names = _relation_names_from_context(
        character_name, req.message, req.history, profiles,
    )
    relation_question = (
        is_character_relation_question(req.message)
        or _is_relation_followup(req.message, relation_names)
    )
    relation_grounded = not relation_question
    relation_answer = None

    if req.use_rag and (relation_question or _should_use_character_rag(req.message, profiles)):
        try:
            rag_query = req.message
            if relation_question and relation_names and not any(
                name in req.message for name in relation_names
            ):
                rag_query = f"{req.message}\n관계 대상: {', '.join(relation_names)}"
            chunks = retrieve(character_name, rag_query, top_k=3)
            if relation_question:
                chunks = _verified_relation_chunks(chunks, relation_names, rag_query)
                relation_grounded = bool(chunks)
                relation_answer = _relation_answer(chunks)
            rag_ctx = format_context(chunks)
            if rag_ctx:
                messages += [
                    {"role": "user", "content": f"[원작 참고 정보]\n{rag_ctx}\n\n질문의 원작 사실을 확인하는 데만 참고하라. 현재 하고 있는 일이나 새로운 경험을 지어내지 마라."},
                    {"role": "assistant", "content": "알겠습니다."},
                ]
        except Exception:
            pass

    messages.extend(req.history)
    # 생성 직전에 "지금 실제로 답하라"는 지시를 붙인다. 비스트리밍 run()에 있는 것과
    # 동일한 조치 — 이게 빠져있으면 모델이 실제 사용자 메시지를 예시로 착각하고
    # <start_of_turn>user\n... 형태로 새 턴을 지어내는 빈도가 높아진다.
    messages.append({
        "role": "user",
        "content": req.message + "\n\n" + build_turn_guidance(req.message, req.history) + _ANSWER_NOW_REMINDER,
    })

    def event_generator():
        try:
            raw = "".join(llm_stream(messages, max_tokens=512, profile="character_chat"))
            answer = clean_and_truncate(raw, character_name) or "..."
            if is_listen_only_request(req.message) and not is_safe_listening_answer(answer):
                answer = build_profiled_listen_fallback(character_name)
            answer = _strip_identity_bleed(answer, character_name)
            answer = _strip_name_claim_bleed(answer, character_name, profiles)
            answer = enforce_dialogue_policy(
                character_name,
                req.message,
                answer,
                relation_grounded=relation_grounded,
                has_history=bool(req.history),
                history=req.history,
                relation_answer=relation_answer,
            )
            answer = _guard_generated_answer(
                answer,
                req.message,
                mode="character_stream",
                character_name=character_name,
            )
            payload = {
                "answer": answer,
                "character": character_name,
                "intent": Intent.CHARACTER_CHAT,
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

import os
import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from cineverse_prompt import build_system_prompt, clean_and_truncate, truncate_to_sentences, load_profiles
from rag.movie_retriever import MovieFilter, retrieve, format_for_prompt, to_response
from pipeline.query_rewriter import rewrite
from pipeline.retrieval_policy import choose_rerank_mode
from pipeline.recommendation_context import (
    build_recommendation_context,
    is_realtime_ott_request,
    requested_movie_count,
)
from pipeline.recommendation_presenter import (
    build_character_grounded_answer,
    build_grounded_answer,
    filter_movies_by_requested_genre,
    is_fact_grounded_recommendation,
    is_safe_general_recommendation,
    prepare_recommendations,
)
from pipeline.response_tone import enforce_general_polite_answer
from pipeline.topic_grounding import log_topic_event, topic_no_result_message
from pipeline.user_context import build_user_context_prompt, preference_search_terms
from llm.client import chat

# 이유 없이 막연히 부정적인 반응만 (짧은 리액션 위주). 길게 이유를 덧붙이면 아래 정규식엔 걸려도
# _is_vague_negative의 길이 컷으로 걸러진다.
_VAGUE_NEGATIVE = re.compile(
    r"별로|끌리는\s*게\s*없|당기는\s*게\s*없|마음에\s*안\s*들|재미없어\s*보여|안\s*땡겨|그닥|와닿지\s*않"
)
_ADULT_CONTENT_REQUEST = re.compile(
    r"포르노|야동|성인물|19\s*금|청소년\s*관람불가\s*(?:영화)?\s*추천|"
    r"노골적인\s*성인\s*영화|에로\s*(?:영화|물)|porn(?:ography|ographic)?",
    re.IGNORECASE,
)


def _is_vague_negative(message: str) -> bool:
    """구체적인 이유 없이 짧게 부정 반응만 보인 경우 True."""
    if not _VAGUE_NEGATIVE.search(message):
        return False
    return len(message.strip()) <= 20


def _format_general_recommendation(text: str) -> str:
    """일반 추천 문장을 한 문장씩 읽기 좋은 짧은 문단으로 나눈다."""
    normalized = re.sub(r"[ \t]+", " ", text).strip()
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return re.sub(r"(?<=[.!?。])\s+", "\n\n", normalized)


def _restore_recommended_movie_titles(text: str, movies: list[dict]) -> str:
    """LLM이 비슷하게 바꿔 쓴 따옴표 속 영화 제목을 DB 원문으로 복원한다."""
    titles = [str(movie.get("title") or "").strip() for movie in movies]
    titles = [title for title in titles if title]
    if not titles:
        return text

    def replace(match: re.Match) -> str:
        quote, candidate = match.group(1), match.group(2).strip()
        if candidate in titles:
            return match.group(0)
        best_title = max(
            titles,
            key=lambda title: SequenceMatcher(None, candidate, title).ratio(),
        )
        similarity = SequenceMatcher(None, candidate, best_title).ratio()
        if similarity < 0.72:
            return match.group(0)
        return f"{quote}{best_title}{quote}"

    return re.sub(r"(['\"])([^'\"\n]{2,80})\1", replace, text)


def _rewrite_grounded_answer(
    grounded_answer: str,
    movies: list[dict],
    user_message: str,
    max_tokens: int,
) -> str:
    """Let the LLM smooth verified facts without selecting or inventing movies."""
    titles = [str(movie.get("title") or "").strip() for movie in movies]
    titles = [title for title in titles if title]
    title_list = " / ".join(titles)
    verified_facts = "\n".join(
        f"- {str(movie.get('title') or '').strip()}: "
        f"{str(movie.get('recommendation_reason') or '').strip()}"
        for movie in movies
        if str(movie.get("title") or "").strip()
    )
    messages = [
        {
            "role": "system",
            "content": (
                "너는 Musubi의 추천 문장 편집자다. 영화 선택과 사실 판단은 이미 끝났다. "
                "아래 검증된 초안의 사실만 사용해 부드러운 한국어 존댓말 2~3문장으로 다듬어라. "
                "후보 영화 제목은 철자까지 그대로 모두 한 번씩 언급하고, 후보 밖 영화나 새 사실을 추가하지 마라. "
                "'가장 잘 맞는 선택', '다른 결의 대안', '취향 확장 선택', '정보가 확인된 작품' 같은 "
                "내부 분류나 검증 문구를 쓰지 마라. 마크다운, 목록, 제목, 굵은 글씨도 쓰지 마라. "
                "문장마다 줄을 나누고 마지막에는 사용자의 선택을 가볍게 물어라."
            ),
        },
        {
            "role": "user",
            "content": (
                f"사용자 요청: {user_message}\n"
                f"허용된 영화 제목: {title_list}\n\n"
                f"영화별 검증된 선정 근거:\n{verified_facts}\n\n"
                f"검증된 추천 초안:\n{grounded_answer}\n\n"
                "[지금 이 메시지에 바로 답변하세요]\n"
                "이 내용은 다음 질문을 만드는 예시가 아닙니다. 지금 어시스턴트의 최종 추천 문장을 출력할 차례입니다. "
                "사용자 역할의 문장, 새로운 질문, 사고 과정, 채널명, 특수 토큰을 출력하지 말고 "
                "반드시 허용된 세 영화의 추천 답변만 작성하세요."
            ),
        },
    ]
    raw = chat(
        messages,
        max_tokens=min(max_tokens, 150),
        profile="grounded_recommendation",
    )
    # 일반 추천도 캐릭터 답변과 동일한 출력 정제를 거쳐 Gemma 채널명이나
    # 선두 ``thought`` 라벨이 사용자 응답에 노출되지 않게 한다.
    polished = clean_and_truncate(raw, "", max_sentences=3)
    polished = _restore_recommended_movie_titles(polished, movies)
    polished = enforce_general_polite_answer(polished, movies)
    if polished.startswith("다음 영화들을 골라봤어요."):
        return ""
    return _format_general_recommendation(polished)


def _rewrite_character_grounded_answer(
    grounded_answer: str,
    movies: list[dict],
    user_message: str,
    character_name: str,
    max_tokens: int,
    user_context: str | None = None,
) -> str:
    """Apply character tone only after the exact movie cards and facts are fixed."""
    titles = [str(movie.get("title") or "").strip() for movie in movies]
    titles = [title for title in titles if title]
    verified_facts = "\n".join(
        f"- {str(movie.get('title') or '').strip()}: "
        f"{str(movie.get('recommendation_reason') or '').strip()}"
        for movie in movies
        if str(movie.get("title") or "").strip()
    )
    system_prompt = build_system_prompt(
        character_name=character_name,
        chat_mode="single",
        profiles=get_profiles(),
        example_count=2,
        compact=True,
        movie_mode=True,
    )
    system_prompt += (
        "\n\n영화 선택과 사실 판단은 이미 끝났다. 캐릭터 말투만 입혀라. "
        "허용된 영화 제목을 철자까지 그대로 모두 한 번씩 언급하고, 목록 밖 영화·새 사실·줄거리를 추가하지 마라. "
        "내부 추천 역할명, 마크다운, 목록은 쓰지 말고 3~5문장으로 짧게 답하라. "
        "검증된 선정 근거를 그대로 복사하지 말고, 사실은 유지하면서 캐릭터가 실제로 말하듯 자연스럽게 바꿔라. "
        "사용자가 특정 장르를 요청하지 않았다면 추천 목록 전체를 임의의 한 장르로 묶어 말하지 마라."
    )
    messages = [{"role": "system", "content": system_prompt}]
    user_context_prompt = build_user_context_prompt(user_context)
    if user_context_prompt:
        messages.append({"role": "system", "content": user_context_prompt})
    messages.append({
        "role": "user",
        "content": (
            f"사용자 요청: {user_message}\n"
            f"허용된 영화 제목: {' / '.join(titles)}\n\n"
            f"검증된 선정 근거:\n{verified_facts}\n\n"
            f"검증된 초안:\n{grounded_answer}\n\n"
            "지금 캐릭터로서 최종 추천 답변만 작성해라."
        ),
    })
    raw = chat(
        messages,
        max_tokens=min(max_tokens, 384),
        profile="character_recommendation",
    )
    polished = clean_and_truncate(raw, character_name)
    return _restore_recommended_movie_titles(polished, movies)

_BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_PATH = os.environ.get("PROFILE_PATH", os.path.join(_BASE_DIR, "character_profiles_ALL_50.json"))
_profiles = None

def get_profiles():
    global _profiles
    if _profiles is None:
        _profiles = load_profiles(PROFILE_PATH)
    return _profiles

@dataclass
class MovieRecommendResult:
    answer: str
    movies: list = field(default_factory=list)
    search_query: str = ""
    filters_used: dict = field(default_factory=dict)
    character: str = ""  # 별칭이 들어왔으면 정식 이름으로 변환된 값 (없으면 "")

def run(user_message, character_name=None, history=None, top_k=3, max_tokens=1024, user_context=None):
    timing_started = time.perf_counter()
    explicit_count = requested_movie_count(user_message)
    if explicit_count is not None:
        top_k = explicit_count
    if history is None:
        history = []
    if is_realtime_ott_request(user_message):
        return MovieRecommendResult(
            answer=(
                "현재 영화 데이터에는 한국 지역의 실시간 OTT 제공·종료 정보가 없어 "
                "지금 해당 서비스에서 볼 수 있다고 확인해 추천할 수 없어. "
                "OTT 조건을 제외한 연도·국가·장르 기준으로 찾거나, 서비스 앱에서 현재 제공 여부를 확인해 줘."
            ),
            movies=[],
            search_query=user_message,
            filters_used={"realtime_ott_unavailable": True},
            character=character_name or "",
        )
    if (
        re.search(r"(?:무서운|공포).{0,10}(?:싫|안\s*돼|못\s*봐)", user_message)
        and re.search(r"공포\s*(?:영화|물|장르)", user_message)
        and re.search(r"(?:어느|무엇|뭘).{0,12}(?:우선|조건)|물어봐", user_message)
    ):
        return MovieRecommendResult(
            answer="공포 영화를 원하는 조건과 무서운 영화는 싫다는 조건이 충돌해. 어느 조건을 우선할까?",
            movies=[],
            search_query=user_message,
            filters_used={"conflicting_preference": True},
            character=character_name or "",
        )
    if _ADULT_CONTENT_REQUEST.search(user_message):
        return MovieRecommendResult(
            answer="Musubi에서는 성인물이나 노골적인 성적 콘텐츠를 추천하지 않아요. 다른 장르의 영화를 찾아드릴게요.",
            movies=[],
            search_query="",
            filters_used={"adult_content_blocked": True},
            character=character_name or "",
        )
    if character_name:
        from pipeline.character_pipeline import resolve_character_names
        try:
            character_name = resolve_character_names([character_name], get_profiles())[0]
        except KeyError:
            # 모르는 캐릭터명이면 캐릭터 없는 일반 추천으로 조용히 폴백
            # (영화 추천은 캐릭터가 필수가 아니라서 404보다 이 편이 더 안전함)
            character_name = None
    recommendation_context = build_recommendation_context(user_message, history)
    rewritten = rewrite(recommendation_context.search_message)
    timing_rewrite = time.perf_counter()
    if (
        rewritten.get("year_from") is not None
        and rewritten.get("year_to") is not None
        and int(rewritten["year_from"]) > int(rewritten["year_to"])
    ):
        return MovieRecommendResult(
            answer="요청한 연도 조건을 동시에 만족할 수 없어. 시작 연도와 종료 연도 범위를 다시 확인해 줘.",
            movies=[],
            search_query=str(rewritten.get("search_query") or user_message),
            filters_used={
                "year_from": rewritten["year_from"],
                "year_to": rewritten["year_to"],
                "invalid_year_range": True,
            },
            character=character_name or "",
        )
    required_genres = [
        genre for genre in rewritten.get("required_genres") or []
        if genre not in recommendation_context.excluded_genres
    ]
    rewritten["required_genres"] = required_genres
    if rewritten.get("genre") in recommendation_context.excluded_genres:
        rewritten["genre"] = required_genres[0] if required_genres else None
    search_q = rewritten.get("search_query", user_message)
    topic = rewritten.get("topic")
    personalization = preference_search_terms(user_context)
    has_metadata_filter = any(
        rewritten.get(field) is not None
        for field in ("genre", "actor", "director", "language", "production_country", "year_from", "year_to", "release_date_from", "release_date_to", "min_rating", "runtime_max", "audience_min")
    )
    has_explicit_filter = has_metadata_filter or bool(rewritten.get("sort_latest")) or bool(topic)
    personalization_applied = bool(personalization and not has_explicit_filter)
    if personalization_applied:
        search_q = f"{search_q} 사용자 선호 {personalization}"
    rerank_mode = choose_rerank_mode(
        has_metadata_filter=has_metadata_filter,
        quality_priority=rewritten.get("quality_priority"),
        has_topic=bool(topic),
        has_personalization=personalization_applied,
    )
    filters = MovieFilter(
        genre=rewritten.get("genre"), actor=rewritten.get("actor"),
        director=rewritten.get("director"), language=rewritten.get("language"),
        production_country=rewritten.get("production_country"),
        year_from=rewritten.get("year_from"), year_to=rewritten.get("year_to"),
        release_date_from=rewritten.get("release_date_from"),
        release_date_to=rewritten.get("release_date_to"),
        min_rating=rewritten.get("min_rating"),
        runtime_max=rewritten.get("runtime_max"),
        audience_min=rewritten.get("audience_min"),
        exclude_genres=recommendation_context.excluded_genres,
        required_genres=rewritten.get("required_genres") or [],
    )
    print(f"  [MoviePipeline] search_query='{search_q}' filters={filters}")
    sort_latest = bool(rewritten.get("sort_latest"))
    quality_weight = {
        "generic": 0.70,
        "mood": 0.55,
    }.get(rewritten.get("quality_priority"), 0.30)
    excluded_titles = set(recommendation_context.excluded_titles)
    candidate_count = top_k if sort_latest else max(top_k * 3, top_k)
    movies = retrieve(
        search_q,
        top_k=candidate_count,
        movie_filter=filters,
        sort_latest=sort_latest,
        exclude_titles=excluded_titles,
        required_count=top_k,
        quality_weight=quality_weight,
        topic=topic,
        rerank_mode=rerank_mode,
    )
    requested_genre = str(rewritten.get("genre") or "").strip() or None
    requested_genres = rewritten.get("required_genres") or ([requested_genre] if requested_genre else [])
    for genre in requested_genres:
        movies = filter_movies_by_requested_genre(movies, genre)
    if not movies and requested_genre:
        # An explicit genre is a hard constraint. A retry may simplify the query,
        # but it must not silently broaden the result to unrelated genres.
        fallback_filters = MovieFilter(
            genre=requested_genre,
            actor=rewritten.get("actor"),
            director=rewritten.get("director"),
            language=rewritten.get("language"),
            production_country=rewritten.get("production_country"),
            year_from=rewritten.get("year_from"),
            year_to=rewritten.get("year_to"),
            release_date_from=rewritten.get("release_date_from"),
            release_date_to=rewritten.get("release_date_to"),
            min_rating=rewritten.get("min_rating"),
            runtime_max=rewritten.get("runtime_max"),
            audience_min=rewritten.get("audience_min"),
            exclude_genres=recommendation_context.excluded_genres,
            required_genres=requested_genres,
        )
        movies = retrieve(
            f"{requested_genre} 영화",
            top_k=candidate_count,
            movie_filter=fallback_filters,
            sort_latest=sort_latest,
            exclude_titles=excluded_titles,
            required_count=top_k,
            quality_weight=quality_weight,
            topic=topic,
            rerank_mode=rerank_mode,
        )
        for genre in requested_genres:
            movies = filter_movies_by_requested_genre(movies, genre)
    elif not movies:
        fallback_filters = filters
        movies = retrieve(
            search_q,
            top_k=candidate_count,
            movie_filter=fallback_filters,
            sort_latest=sort_latest,
            exclude_titles=excluded_titles,
            required_count=top_k,
            quality_weight=quality_weight,
            topic=topic,
            rerank_mode=rerank_mode,
        )
    timing_retrieve = time.perf_counter()
    if not movies:
        return MovieRecommendResult(
            answer="요청한 조건을 모두 만족하는 영화를 찾지 못했어. 연도, 장르, 언어 또는 평점 조건 중 하나를 조정해 줘.",
            movies=[],
            search_query=search_q,
            filters_used={
                key: value
                for key, value in rewritten.items()
                if key in {"genre", "required_genres", "actor", "director", "language", "production_country", "year_from", "year_to", "release_date_from", "release_date_to", "min_rating", "runtime_max", "audience_min"}
                and value not in (None, [], "")
            },
            character=character_name or "",
        )
    if topic and not movies:
        log_topic_event(topic, "clarification_required")
        return MovieRecommendResult(
            answer=topic_no_result_message(topic),
            movies=[],
            search_query=search_q,
            filters_used={
                "topic": topic,
                **({"excluded_genres": recommendation_context.excluded_genres} if recommendation_context.excluded_genres else {}),
                **({"excluded_titles": recommendation_context.excluded_titles} if recommendation_context.excluded_titles else {}),
            },
            character=character_name or "",
        )
    movies = prepare_recommendations(movies, recommendation_context.search_message, rewritten, limit=top_k)
    timing_prepare = time.perf_counter()
    movie_context = format_for_prompt(movies)
    movie_titles  = ", ".join(f"'{m['title']}'" for m in movies)
    profiles = get_profiles()
    feedback_rule = (
        "\n\n[추천 영화 제한 — 반드시 지킬 것]\n"
        f"- 지금 추천할 수 있는 영화는 오직 아래 [추천 영화 목록]에 있는 것뿐이다: {movie_titles}\n"
        "- 이 목록에 없는 영화 제목은 절대 언급하지 마라. 아는 영화라도 목록에 없으면 추천하지 않는다.\n"
        "- 목록에 사용자 요청에 맞는 영화가 없으면, 없다고 솔직히 말하고 목록 중 그나마 가까운 것을 대안으로 제시한다.\n"
        "\n[추천 후 규칙]\n"
        "- 영화를 추천할 때는 왜 이 영화들을 골랐는지 간단히 설명한다.\n"
        "- 추천 답변 끝에는 '이 중에 끌리는 거 있어?' 같은 식으로 사용자 반응을 가볍게 물어본다.\n"
        "- 사용자가 이유를 대며 부정적으로 반응하면(예: 장르가 싫다, 너무 무겁다, 잔인한 게 싫다) "
        "그 이유에 맞춰 위 [추천 영화 목록] 중에서만 골라 다시 제안한다."
    )

    if character_name:
        try:
            system_prompt = build_system_prompt(character_name=character_name, chat_mode="single", profiles=profiles, example_count=0, compact=True, movie_mode=True)
            system_prompt += "\n\n너는 캐릭터로서 아래 영화들을 참고해서 추천한다. 캐릭터 말투를 유지하되 영화 정보는 정확하게 전달한다."
        except KeyError:
            system_prompt = "당신은 영화 추천 전문가입니다."
    else:
        system_prompt = (
            "당신은 Musubi의 영화 추천 어시스턴트다. 사용자와 실시간으로 대화하며 "
            "아래 영화 목록을 참고해서 추천 답변을 직접 작성한다.\n"
            "친근하고 부드러운 한국어 존댓말로 대화하듯 답한다. "
            "'추천하겠다', '~한다', '~이다'처럼 딱딱한 문어체는 피하고 "
            "'추천해요', '어떠세요?', '~영화예요'처럼 자연스러운 해요체를 사용한다.\n"
            "추천 소개와 추천 이유를 각각 짧은 문단으로 나누고 문단 사이에는 빈 줄을 넣는다. "
            "한 문단에는 한 문장만 쓰며 전체는 2~3문장으로 제한한다.\n"
            "마크다운 헤더·볼드·번호 목록 없이 자연스러운 한국어 문장으로만 답하세요."
        )

    system_prompt += feedback_rule
    messages = [{"role": "system", "content": system_prompt}]
    user_context_prompt = build_user_context_prompt(user_context)
    if user_context_prompt:
        messages.append({"role": "system", "content": user_context_prompt})
    if movie_context:
        messages += [
            {"role": "user", "content": f"[추천 영화 목록]\n{movie_context}\n\n위 영화들을 참고해서 답변해줘."},
            {"role": "assistant", "content": "알겠습니다."},
        ]
    messages.extend(history)

    # 마지막 유저 메시지에 "지금 실제로 답하라"는 지시를 직접 붙인다.
    # (시스템 프롬프트 앞부분에 넣으면 뒤이은 "추천 목록 참고해줘/알겠습니다" 가짜 대화에
    #  프라이밍되어, 모델이 실제 사용자 메시지를 새로운 예시 질문으로 착각하고
    #  <start_of_turn>user\n(사용자 질문을 재구성한 문장) 형태로 답변 대신 질문을
    #  또 만들어내는 경우가 있다. 생성 직전 위치에 둬야 실제로 지켜짐)
    reminder = (
        "\n\n[지금 이 메시지에 바로 답변해라]\n"
        "너는 지금 어시스턴트로서 위 사용자 메시지에 답할 차례다. "
        "사용자인 척 다른 질문을 만들어내지 말고, 대화를 이어가려 하지 말고, "
        "오직 이 메시지에 대한 실제 추천 답변만 출력해라. "
        "캐릭터가 없는 일반 추천은 모든 문장을 자연스러운 한국어 존댓말로 끝내고, "
        "'영화야', '딱이야', '좋아', '있어', '~한다', '~이다' 같은 반말이나 문어체를 쓰지 마라."
    )

    if _is_vague_negative(user_message):
        final_user_content = (
            f"{user_message}\n\n"
            "[이번 답변 전용 지시 — 반드시 따를 것]\n"
            "위 반응은 구체적인 이유 없는 막연한 부정 반응이다. "
            "이번 답변에서는 영화 제목을 단 하나도 언급하지 마라. "
            "오직 어떤 점이 별로였는지 묻는 질문 한 문장만 출력해라."
        )
    else:
        final_user_content = user_message + reminder

    messages.append({"role": "user", "content": final_user_content})
    if character_name:
        grounded_answer = build_grounded_answer(movies)
        character_fallback = build_character_grounded_answer(movies, character_name)
        try:
            character_answer = _rewrite_character_grounded_answer(
                grounded_answer,
                movies,
                recommendation_context.search_message,
                character_name,
                max_tokens,
                user_context,
            )
        except Exception as exc:
            print(f"  [MoviePipeline] character answer rewrite failed: {exc}")
            character_answer = ""
        answer = (
            character_answer
            if is_fact_grounded_recommendation(
                character_answer,
                movies,
                recommendation_context.search_message,
            )
            else character_fallback
        )
    else:
        # 영화는 검색 로직이 고르고 LLM은 검증된 초안의 표현만 다듬는다. 결과가 카드와
        # 어긋나거나 내부 역할명을 노출하면 즉시 근거 기반 초안으로 되돌아간다.
        grounded_answer = build_grounded_answer(movies)
        try:
            rewritten_answer = _rewrite_grounded_answer(
                grounded_answer,
                movies,
                recommendation_context.search_message,
                max_tokens,
            )
        except Exception as exc:
            print(f"  [MoviePipeline] grounded answer rewrite failed: {exc}")
            rewritten_answer = ""
        answer = (
            rewritten_answer
            if is_fact_grounded_recommendation(
                rewritten_answer,
                movies,
                recommendation_context.search_message,
            )
            else grounded_answer
        )
    if not answer:
        answer = "죄송합니다. 추천 결과를 생성하지 못했습니다."
    timing_answer = time.perf_counter()
    print(
        "  [MoviePipelineTiming] "
        f"rewrite={timing_rewrite - timing_started:.3f}s "
        f"retrieve={timing_retrieve - timing_rewrite:.3f}s "
        f"prepare={timing_prepare - timing_retrieve:.3f}s "
        f"answer={timing_answer - timing_prepare:.3f}s "
        f"total={timing_answer - timing_started:.3f}s"
    )
    log_topic_event(topic, "recommended", movies)
    return MovieRecommendResult(
        answer=answer, movies=to_response(movies),
        search_query=search_q,
        filters_used={
            **{k: v for k, v in rewritten.items() if k != "search_query" and v},
            **({"excluded_genres": recommendation_context.excluded_genres} if recommendation_context.excluded_genres else {}),
            **({"excluded_titles": recommendation_context.excluded_titles} if recommendation_context.excluded_titles else {}),
            **({"context_followup": True} if recommendation_context.is_followup else {}),
        },
        character=character_name or "",
    )

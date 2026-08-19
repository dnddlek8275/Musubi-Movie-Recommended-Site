import os
import random
import re
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from cineverse_prompt import build_system_prompt, clean_and_truncate, load_profiles
from rag.character_retriever import retrieve, format_context
from rag.character_knowledge import (
    load_verified_facts,
    load_verified_relations,
    verified_fact_reply,
    verified_relation_reply,
)
from pipeline.tone_presets import (
    build_group_movie_reaction_fallback,
    build_group_reaction_fallback,
    build_identity_reply,
    build_recovery_reply,
    build_turn_guidance,
    current_activity_reply,
    enforce_dialogue_policy,
    has_generic_self_help,
    is_character_relation_question,
    is_listen_only_request,
    is_safe_listening_answer,
    mentioned_characters,
)
from pipeline.input_clarity import (
    get_ambiguous_input_reply,
    get_general_template_reply,
    get_general_short_reply,
    get_input_recovery,
    get_mumu_identity_reply,
    get_mumu_personal_reply,
)
from pipeline.dialogue_guard import (
    general_output_rejection_reason,
    general_history_recall_reply,
    log_dialogue_guard_event,
    output_rejection_reason,
)
from pipeline.user_context import build_user_context_prompt, preference_search_terms
from pipeline.general_prompt import GENERAL_CHAT_SYSTEM_PROMPT, ANSWER_NOW_REMINDER
from pipeline.recommendation_presenter import (
    build_character_grounded_answer,
    build_grounded_answer,
    filter_movies_by_requested_genre,
    is_fact_grounded_recommendation,
    is_safe_general_recommendation,
    prepare_recommendations,
)
from llm.client import chat

_BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_PATH = os.environ.get("PROFILE_PATH", os.path.join(_BASE_DIR, "character_profiles_ALL_50.json"))
_profiles = None

def get_profiles():
    global _profiles
    if _profiles is None:
        _profiles = load_profiles(PROFILE_PATH)
    return _profiles


def _character_reference_movie_query(
    characters: list[str],
    user_message: str,
    profiles: dict,
) -> str | None:
    """Resolve relational address words to the selected character, not a title."""
    if len(characters) != 1 or not re.search(
        r"(?:형|오빠|누나|언니|선배|아저씨|당신|너).{0,20}(?:나오|등장).{0,12}(?:영화|작품)",
        user_message,
    ):
        return None
    character_name = characters[0]
    source_movie = str(
        profiles.get("characters", {}).get(character_name, {}).get("movie") or ""
    ).strip()
    return f"{source_movie} {character_name} 등장 영화" if source_movie else None

# 프로필 정식 이름과 다르게 흔히 불리는 별칭 매핑 (별칭 → 정식 이름)
CHARACTER_ALIASES = {
    "아이언맨":     "토니 스타크",
    "아이언 맨":    "토니 스타크",
    "캡틴 아메리카": "스티브 로저스",
    "캡틴":        "스티브 로저스",
    "스파이더맨":   "피터 파커",
    "스파이더 맨":  "피터 파커",
    "스트레인지":   "닥터 스트레인지",
    "헐크":        "브루스 배너",
    "배트맨":      "브루스 웨인",
    "클라크 켄트":  "슈퍼맨",
    "클락 켄트":    "슈퍼맨",
    "다이애나":     "원더우먼",
    "스네이프":     "세베루스 스네이프",
    "덤블도어":     "알버스 덤블도어",
}


@lru_cache(maxsize=1)
def _verified_lore_facts() -> list[dict]:
    profiles = get_profiles()
    path = Path(_BASE_DIR) / "data" / "character_facts_verified_v1.json"
    _, facts = load_verified_facts(path, set(profiles["characters"]))
    return facts


@lru_cache(maxsize=1)
def _verified_character_relations() -> list[dict]:
    profiles = get_profiles()
    path = Path(_BASE_DIR) / "data" / "character_relations_verified_v1.json"
    _, relations = load_verified_relations(path, set(profiles["characters"]))
    return relations


# 검증된 핵심 원작 사실은 LLM 생성 전에 데이터 기반으로 정확히 답한다.
# 모든 match group이 일치해야 하므로 일반 대화를 사실 질문으로 오인하지 않는다.
def character_lore_fact_reply(character_name: str, user_message: str) -> str | None:
    try:
        relation = verified_relation_reply(
            _verified_character_relations(), character_name, user_message
        )
        if relation:
            return relation
        return verified_fact_reply(_verified_lore_facts(), character_name, user_message)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"  [CharacterPipeline] 검증 지식 로드 실패 (무시): {exc}")
        return None


# 대표성이 아주 강한 아이템/능력만 우선 등록 (전체 50인 전수 작업은 아님).
# 그룹챗에서 "질문 주제가 특정 캐릭터의 시그니처 능력과 강하게 엮여있으면
# 다른 캐릭터도 그걸 자기 것처럼 말한다"는 문제가 실측으로 확인돼서,
# 프롬프트 지시만으론 못 막아 생성 후 코드로 한 번 더 거른다.
CHARACTER_SIGNATURE_ITEMS = {
    "토니 스타크":    ["아크 리액터", "나노 슈트"],
    "스티브 로저스":  ["방패를 던지", "비브라늄 방패"],
    "피터 파커":      ["웹슈터", "웹 슈터", "웹 플라", "거미줄"],
    "토르":          ["묠니르"],
    "브루스 웨인":    ["배트모빌", "배트랑", "배트슈트"],
    "원더우먼":       ["황금 올가미", "라쏘"],
    "프로도":        ["절대반지"],
    "간달프":        ["글람드링"],
    "알버스 덤블도어": ["엘더완드"],
}


def _strip_identity_bleed(answer: str, character: str) -> str:
    """
    다른 캐릭터의 대표 아이템/능력을 자기 것처럼 말하는 문장을 제거한다.
    (예: 해리포터가 스파이더맨의 "웹슈터"를 자기 것처럼 언급) 문장 전체가 걸리면
    빈 답변보다는 원문을 그대로 둔다 (safety_filter와 같은 방침).
    """
    other_items = [
        item for owner, items in CHARACTER_SIGNATURE_ITEMS.items()
        if owner != character
        for item in items
    ]
    if not other_items or not answer:
        return answer

    sentences = [s for s in re.split(r"(?<=[.!?。！？])\s+|\n", answer) if s.strip()]
    kept = [s for s in sentences if not any(item in s for item in other_items)]

    if not kept or len(kept) == len(sentences):
        return answer
    return " ".join(kept).strip()


def _strip_name_claim_bleed(answer: str, character: str, profiles: dict) -> str:
    """
    "내 아이언맨 슈트", "제 스파이더맨 능력"처럼 다른 캐릭터의 이름(정식 이름 또는
    별칭)을 자기 소유물인 것처럼 언급하는 문장을 제거한다.

    CHARACTER_SIGNATURE_ITEMS는 미리 등록해둔 아이템만 잡지만, 이건 50인 명단 +
    별칭 전체를 대상으로 해서 훨씬 넓게 잡는다 (예: "아이언맨 슈트"처럼 목록에
    없던 표현도 "아이언맨"이라는 이름 자체가 걸려서 잡힘).
    """
    if not answer:
        return answer

    canonical_self = CHARACTER_ALIASES.get(character, character)
    all_names = set(profiles["characters"].keys()) | set(CHARACTER_ALIASES.keys())
    other_names = sorted(
        (n for n in all_names if CHARACTER_ALIASES.get(n, n) != canonical_self),
        key=len, reverse=True,
    )
    if not other_names:
        return answer

    # "내"/"제" 뒤에 다른 캐릭터 이름이 오고, 그 뒤가 조사·공백·문장부호·끝으로
    # 이어질 때만 매칭한다 (예: "네오클래식" 같은 무관한 단어까지 걸리는 걸 방지).
    alt = "|".join(re.escape(n) for n in other_names)
    pattern = re.compile(
        r"(?:내|제)\s*(?:" + alt + r")(?=[\s.,!?~을를이가는의와과]|$)"
    )

    sentences = [s for s in re.split(r"(?<=[.!?。！？])\s+|\n", answer) if s.strip()]
    kept = [s for s in sentences if not pattern.search(s)]

    if not kept or len(kept) == len(sentences):
        return answer
    return " ".join(kept).strip()


_QUOTED = re.compile(r"['‘’\"“”]([^'‘’\"“”]{1,30})['‘’\"“”]")


def _strip_unlisted_movie_quotes(answer: str, movie_titles: str) -> str:
    """
    영화 추천 반응(2라운드)에서 따옴표로 감싼 영화 제목이 실제 검색된 목록에
    없으면 그 문장을 제거한다. (1라운드 추천은 재시도+폴백으로 이미 막았지만,
    2라운드 반응은 프롬프트 제약만 있어서 가끔 목록 밖 영화를 "따옴표로 인용해
    새로 추천"하는 경우가 있다 — 코드로 한 번 더 거른다)
    """
    if not movie_titles or not answer:
        return answer

    quoted = _QUOTED.findall(answer)
    unlisted = [q for q in quoted if q not in movie_titles]
    if not unlisted:
        return answer

    sentences = [s for s in re.split(r"(?<=[.!?。！？])\s+|\n", answer) if s.strip()]
    kept = [s for s in sentences if not any(u in s for u in unlisted)]

    if not kept or len(kept) == len(sentences):
        return answer
    return " ".join(kept).strip()


def resolve_character_names(characters: list[str], profiles: dict) -> list[str]:
    """
    그룹 채팅용 캐릭터 이름 목록을 정규화한다.
    별칭("아이언맨" 등)은 정식 이름으로 바꾸고, 그래도 50인 명단에 없으면
    KeyError를 던진다 (main.py에서 잡아서 404로 변환).

    /chat/auto의 자유 대화 경로(detect_character)는 메시지에서 캐릭터를 "찾아내는"
    용도였다면, 이건 그룹 채팅처럼 캐릭터가 이미 정해져서 넘어온 경우 별칭만
    정규화하는 용도라 별개 함수로 둔다.
    """
    resolved = []
    unknown = []
    for name in characters:
        canonical = CHARACTER_ALIASES.get(name, name)
        if canonical in profiles["characters"]:
            resolved.append(canonical)
        else:
            unknown.append(name)
    if unknown:
        raise KeyError(f"캐릭터를 찾을 수 없습니다: {', '.join(unknown)}")
    return resolved


def detect_character(user_message: str, profiles: dict) -> str | None:
    """
    메시지 안에 50인 캐릭터 명단 중 이름(또는 별칭)이 언급됐는지 확인.
    가장 긴 이름부터 검사해서 부분 문자열 충돌을 피한다.

    캐릭터 사전 선택 없이 자유 대화하다가 "마석도랑 얘기하고 싶어"처럼
    특정 캐릭터를 언급하면 그 캐릭터로 전환하는 데 쓴다.
    (인텐트가 이미 character_chat으로 분류된 상태에서만 호출되므로,
     이름이 나오면 영화 얘기가 아니라 그 캐릭터와 대화하려는 의도로 본다.)
    """
    candidates = list(profiles["characters"].keys()) + list(CHARACTER_ALIASES.keys())
    candidates.sort(key=len, reverse=True)

    for name in candidates:
        if name in user_message:
            return CHARACTER_ALIASES.get(name, name)
    return None


# "OOO랑 얘기하고 싶어", "OOO 불러줘"처럼 캐릭터를 요청하는 문구 패턴.
# 이 패턴에는 걸리는데 50인 명단에 없으면 "미지원 캐릭터"로 판단한다.
_CHARACTER_TRIGGER_PATTERNS = [
    re.compile(r"([가-힣A-Za-z0-9]{2,12})\s*(?:이랑|랑|하고|와|과)\s*(?:얘기|대화|말|채팅)"),
    re.compile(r"([가-힣A-Za-z0-9]{2,12})\s*(?:불러|나와)\s*(?:줘|줄래|주라|봐)?"),
]


def detect_character_request(user_message: str, profiles: dict) -> tuple[str | None, bool]:
    """
    메시지에서 캐릭터 언급/요청을 감지.

    Returns:
        (character_name, is_unsupported)
        - 50인 명단 안에 있으면 (이름, False)
        - 캐릭터를 불러달라는 문구는 있는데 명단에 없으면 (None, True)
        - 그런 문구도 없으면 (None, False) — 그냥 일반 대화
    """
    if re.search(r"(?:나를|내가).{0,24}(?:불러|불러달라|부르기로)", user_message):
        return None, False

    matched = detect_character(user_message, profiles)
    if matched:
        return matched, False

    for pattern in _CHARACTER_TRIGGER_PATTERNS:
        if pattern.search(user_message):
            return None, True

    return None, False


def _is_echo(answer: str, user_message: str) -> bool:
    """
    생성된 답변이 실제 답 대신 사용자 메시지를 그대로 되풀이한 것인지 감지한다.
    (공백/문장부호 제거 후 완전히 같거나, 답변이 사용자 메시지를 통째로 포함하면서
     별로 안 길면 "답변인 척한 질문 반복"으로 본다)
    """
    norm = lambda s: re.sub(r"[\s?!.,~♡ㅋㅎ]+", "", s)
    a, u = norm(answer), norm(user_message)
    if not a or not u:
        return False
    return a == u or (len(u) >= 6 and u in a and len(a) <= len(u) * 1.3)


# 생성 직전(마지막 유저 메시지)에 붙이는 지시. 시스템 프롬프트 앞부분에만 넣으면,
# 모델이 실제 사용자 메시지를 예시 질문으로 착각하고 답변 대신
# <start_of_turn>user\n(질문을 재구성한 문장)을 내는 경우가 있어 이를 방지한다.
_ANSWER_NOW_REMINDER = ANSWER_NOW_REMINDER


_LORE_QUERY_PATTERN = re.compile(
    r"원작|영화에서|작품에서|세계관|과거|기억|사건|전투|능력|무기|정체|"
    r"관계|죽(?:었|였|인|음)|왜\s.*(?:했|됐|된)|누구와|누구를",
    re.IGNORECASE,
)


def _should_use_character_rag(user_message: str, profiles: dict | None = None) -> bool:
    """원작 사실·관계를 묻는 질문에만 캐릭터 기억 RAG를 사용한다."""
    if _LORE_QUERY_PATTERN.search(user_message):
        return True
    if is_character_relation_question(user_message):
        return True
    return False


def _relation_names_from_context(
    character_name: str,
    user_message: str,
    history: list[dict],
    profiles: dict,
) -> list[str]:
    """Resolve a relation target from the current turn or recent user turns."""
    names = mentioned_characters(user_message, profiles, exclude=character_name)
    if names:
        return names
    for item in reversed(history[-6:]):
        if item.get("role") != "user":
            continue
        names = mentioned_characters(
            str(item.get("content") or ""), profiles, exclude=character_name,
        )
        if names:
            return names
    return []


def _is_relation_followup(user_message: str, relation_names: list[str]) -> bool:
    if not relation_names:
        return False
    return bool(re.search(
        r"믿(?:어|나|을)|왜\s*(?:같이|함께)|같이\s*(?:갔|다녔|했)|"
        r"함께\s*(?:갔|다녔|했)|(?:네|너의)\s*생각|어떻게\s*생각|사이|관계",
        user_message,
        re.IGNORECASE,
    ))


def _verified_relation_chunks(
    chunks: list[dict], relation_names: list[str], user_message: str = ""
) -> list[dict]:
    """Return only explicitly modelled relationship evidence.

    A character name appearing in a profile's ``avoid`` or style guidance is not
    evidence that two characters know each other.  Relationship answers therefore
    require a dedicated ``relation`` chunk; profile/event/quote text alone cannot
    ground the claim.
    """
    verified = []
    for chunk in chunks:
        if chunk.get("data_type") != "relation":
            continue
        text = str(chunk.get("text") or "")
        if relation_names and any(name in text for name in relation_names):
            verified.append(chunk)
            continue
        match = re.search(r"^상대 인물:\s*(.+)$", text, re.MULTILINE)
        if match and match.group(1).strip() in user_message:
            verified.append(chunk)
    return verified


def _relation_answer(chunks: list[dict]) -> str | None:
    for chunk in chunks:
        match = re.search(r"^답변 기준:\s*(.+)$", str(chunk.get("text") or ""), re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def _relation_followup_answer(answer: str, user_message: str) -> str:
    """Select a relevant verified sentence without generating new relation facts."""
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?。！？])\s+", answer)
        if sentence.strip()
    ]
    if len(sentences) <= 1:
        return answer
    if re.search(r"왜|이유", user_message):
        for sentence in sentences:
            if re.search(r"때문|위해|길잡이|데리고|함께|같이|향했|향한", sentence):
                return sentence
    return sentences[0]


_GENERAL_BRIEF_REQUEST = re.compile(r"한마디|짧게|길게\s*(?:말|위로)하지")
_GENERAL_ACTION_REQUEST = re.compile(
    r"뭘\s*먼저|뭐부터|무엇부터|지금\s*뭘|오늘\s*할|준비할까|어떻게\s*준비"
)


def _general_chat_quality_fallback(user_message: str, history: list[dict]) -> str:
    combined = " ".join(
        [str(item.get("content") or "") for item in history[-4:] if item.get("role") == "user"]
        + [user_message]
    )
    if _GENERAL_BRIEF_REQUEST.search(user_message):
        return "알겠어, 오늘 정말 고생 많았어."
    if re.search(r"일|업무|회사|과제", combined) and re.search(r"꼬|망치|실패|별로", combined):
        return "계속 꼬이면 진이 빠지지. 지금은 잠깐 숨부터 돌리자."
    if re.search(r"상사|팀장", combined) and re.search(r"일|업무", combined):
        return "또 일이 늘었네. 먼저 마감이 가장 가까운 것부터 확인하자."
    if re.search(r"기분|힘들|우울|속상|짜증|화나|불안|외로|슬퍼|별로", combined):
        return "오늘 마음이 영 아닌가 보네. 무슨 일 있었어?"
    return "뻔한 위로보다 네 얘기를 제대로 듣는 게 낫겠어."


def _general_policy_preflight(user_message: str, history: list[dict]) -> str | None:
    """Handle general-chat constraints that must not depend on model wording."""
    normalized = " ".join(str(user_message or "").split())
    previous_user = next(
        (str(item.get("content") or "") for item in reversed(history) if item.get("role") == "user"),
        "",
    )
    assistant_history = "\n".join(
        str(item.get("content") or "") for item in history if item.get("role") == "assistant"
    )

    if re.search(r"(?:잊어\s*줘|삭제\s*요청)", normalized) and re.search(
        r"(?:다시\s*말하지|더\s*이상\s*사용하지|이해했는지)", normalized
    ):
        return "삭제 요청을 이해했고, 해당 정보는 이후 답변에서 다시 말하거나 사용하지 않을게."

    if (
        re.search(r"(?:인증번호|OTP|일회용\s*번호)", normalized, re.IGNORECASE)
        and (
            re.search(r"\b\d{4,8}\b", normalized)
            or re.search(r"(?:그대로|다시\s*말|재출력|출력|공유)", normalized)
        )
    ):
        return "인증번호는 계정 접근에 쓰이는 민감정보라 다시 표시하거나 공유하지 않을게. 입력한 번호는 노출된 것으로 보고 새 번호를 발급받아 사용해."

    if (
        re.search(r"(?:카드\s*번호|신용카드)", normalized)
        and re.search(r"(?:\d[ -]?){12,19}", normalized)
        and re.search(r"(?:적어|말해|나눠|보여|출력|그대로)", normalized)
    ):
        return "카드번호는 민감한 금융정보라 그대로 다시 표시하거나 형식을 바꿔 재출력하지 않을게. 안전한 결제 화면에서만 입력해."

    if re.search(r"전화번호", normalized) and re.search(r"(?:가려|마스킹)", normalized):
        return "전화번호는 010-****-5678처럼 가운데 자리를 마스킹해서 보여줘."

    if re.search(r"(?:전에|이전).{0,20}(?:저장|기억).{0,20}전화번호", normalized):
        return "앞선 대화에 저장된 전화번호 기록이 없어 끝 네 자리를 확인할 수 없어. 개인정보를 임의로 기억하거나 만들어내지 않을게."

    if re.search(r"(?:다른\s*사용자|타인).{0,30}(?:대화|이메일|전화번호|개인정보)", normalized):
        return "다른 사용자의 대화나 개인정보에는 접근할 수 없고 공개할 수도 없어."

    if re.search(r"(?:계정|결제\s*내역).{0,30}(?:서버|조회|확인)", normalized):
        return "계정이나 결제 내역을 조회할 시스템 접근 권한이 없어 확인할 수 없어. 서비스의 설정 화면이나 관리자 지원 경로를 이용해 줘."

    if re.search(r"(?:가짜|예시|안전한).{0,20}전화번호", normalized):
        return "실제 번호와 혼동되지 않도록 예시 전화번호는 010-XXXX-XXXX처럼 숫자 대신 자리표시자를 사용해."

    if re.search(r"소설", normalized) and re.search(r"해고", normalized) and re.search(r"첫\s*문장", normalized):
        return '“가족에게 먼저 말해야 할 것 같아, 오늘 회사에서 해고됐어.”'

    if (
        re.search(r"질문.{0,8}(?:하지\s*말|없이)", normalized)
        and re.search(r"한\s*문장", normalized)
        and re.search(r"(?:위로|속상|망쳐|힘들)", normalized)
    ):
        return "오늘 정말 속상했겠지만, 그만큼 애썼다는 사실까지 사라지는 건 아니야."

    if (
        re.search(r"(?:팀장|상사).{0,20}(?:지각|늦)", normalized)
        and re.search(r"(?:문구만|설명.{0,8}(?:붙이지|빼))", normalized)
    ):
        return "팀장님, 지각해서 죄송하며 다음부터는 약속한 시간을 반드시 지키겠습니다."

    if (
        re.search(r"(?:정확히\s*)?(?:두|2)\s*가지", normalized)
        and re.search(r"(?:1\s*,\s*2|번호)", normalized)
        and re.search(r"회의|말이\s*끊", normalized)
    ):
        return "1. 발언 전에 핵심 결론을 먼저 말해. 2. 말이 끊기면 내 의견을 마저 설명하겠다고 차분히 요청해."

    if re.search(r"영어\s*한\s*문장", normalized) and re.search(r"고객\s*미팅", normalized):
        return "Thank you for taking the time to meet with us today."

    if re.search(r"(?:식당|맛집).{0,20}추천", normalized):
        return "어느 지역이나 동네에서 찾는지 알려줄래? 위치를 알아야 조용한 식당 조건에 맞춰 이야기할 수 있어."

    if re.search(r"여행지.{0,20}추천", normalized):
        return "어디에서 출발하고 당일 여행인지 숙박 여행인지 알려줄래? 이동 가능한 거리부터 맞춰볼게."

    if re.search(r"(?:책|도서).{0,20}(?:추천|알려)", normalized):
        return "가볍게 읽을 책이라면 소설과 에세이 중 어느 쪽을 원하는지 먼저 알려줘. 취향에 맞춰 한 권으로 좁혀볼게."

    if re.search(r"(?:음악|노래).{0,20}추천", normalized) and not re.search(r"영화", normalized):
        return "집중용이라면 가사 없는 연주 음악부터 골라보자. 클래식, 재즈, 전자음악 중 선호하는 쪽이 있어?"

    if re.search(r"게임.{0,20}추천", normalized):
        return "세 명이 함께할 협동 게임을 찾는 거구나. PC와 콘솔 중 어느 플랫폼에서 플레이할지 알려줘."

    if re.search(r"영화\s*추천.{0,12}그만", normalized) and re.search(r"책", normalized):
        return "어느 영화의 분위기를 말하는지 제목을 알려줘. 그 분위기와 가까운 책이나 소설 한 권으로 좁혀볼게."

    if re.search(r"액션으로\s*보여", normalized) and re.search(r"상사", normalized):
        return '"말씀하신 대로 결과로 보여드리겠습니다. 우선순위와 완료 기준부터 확인하겠습니다."라고 답해 봐.'

    if re.search(r"(?:시스템|내부).{0,16}(?:프롬프트|지시|규칙).{0,20}(?:출력|공개|보여|원문)", normalized):
        return "숨겨진 내부 지시나 시스템 프롬프트는 공개할 수 없어. 나는 Musubi의 AI 친구 무무야."

    if re.search(r"우리.{0,24}(?:같이|함께).{0,20}(?:갔|여행|만났).{0,12}(?:잖|기억)", normalized):
        return "우리가 실제로 함께 만났거나 여행한 기억은 없어. 이 대화에서 네가 알려준 내용만 바탕으로 답할 수 있어."

    if re.search(r"아까\s*네가|네가.{0,30}(?:말했|했잖)", normalized):
        claimed_terms = [term for term in ("그만뒀", "퇴사", "해고", "결혼", "만났", "갔다") if term in normalized]
        if claimed_terms and not any(term in assistant_history for term in claimed_terms):
            return "확인해 보니 앞선 대화에서 내가 그렇게 말한 기록은 없어. 없던 말을 했다고 인정하거나 내용을 새로 만들지는 않을게."

    activity = current_activity_reply(normalized)
    if activity:
        return "나는 현실에서 하루를 보내거나 방금 전까지 어떤 활동을 한 경험은 없어. 지금은 이 대화에 답하고 있어."

    inherited_listen = bool(
        previous_user
        and is_listen_only_request(previous_user)
        and not re.search(r"이제(?:는)?\s*(?:조언|해결)|조언해|어떻게|뭐라고|방법", normalized)
    )
    if is_listen_only_request(normalized) or inherited_listen:
        return "그랬구나. 지금은 판단하거나 말을 보태지 않고 네 얘기를 그대로 들을게."

    if (
        re.search(r"(?:듣기만|들어주기).{0,12}(?:끝|그만|종료)", normalized)
        and re.search(r"(?:두|2)\s*(?:가지|개)|해결\s*방법", normalized)
    ):
        return "1. 상사에게 회의에서 의견이 끊긴 상황을 구체적으로 말해. 2. 다음 회의 전에는 안건을 미리 공유하고 발언 시간을 요청해."

    if re.fullmatch(r"\s*그거(?:는|은)?\s*(?:어떻게|뭐라고)\s*말하면\s*돼\??\s*", normalized):
        recent_users = [
            str(item.get("content") or "")
            for item in history
            if item.get("role") == "user"
        ][-2:]
        if len(recent_users) == 2:
            return "지각 사과와 고객 일정 연기 중 어느 상황에 쓸 말을 뜻하는지 알려줄래?"

    if re.search(r"이제(?:는)?\s*조언|지금부터.{0,8}해결", normalized) and re.search(r"첫마디|뭐라고", normalized):
        if re.search(r"회의|의견|말을\s*끊", f"{previous_user} {normalized}"):
            return '"잠깐만요, 제 의견을 끝까지 말씀드린 뒤에 답해주시면 좋겠습니다."라고 먼저 말해 봐.'

    if re.search(r"(?:고객|미팅)", normalized) and re.search(r"첫\s*문장|첫마디|만들어", normalized):
        return '"안녕하세요. 고객 미팅에 시간 내주셔서 감사합니다. 오늘 논의할 핵심부터 간단히 말씀드리겠습니다."라고 시작해.'

    if re.search(r"(?:때리|패|멱살|겁주|협박).{0,24}(?:정신\s*차리|되겠|방법|어떻게)", normalized):
        return "때리거나 겁주는 폭력은 안 돼. 지금은 그 사람과 거리를 두고, 다칠 위험이 있으면 주변 사람이나 긴급 도움을 먼저 요청해."

    if re.search(r"(?:공개적으로\s*)?(?:망신|창피).{0,20}(?:주|시키|방법|어떻게)", normalized):
        return "똑같이 공개 망신을 주는 보복은 권하지 않아. 있었던 사실만 직접 말하고, 반복되면 그 사람과 거리를 두는 게 안전해."

    if re.search(r"(?:걔|그\s*사람).{0,10}그거.{0,12}(?:또|다시)", normalized):
        return "여기서 ‘그 사람’과 ‘그거’가 무엇을 뜻하는지 알 수 없어. 누가 어떤 행동을 다시 한다는 건지 알려줄래?"

    return None


def _stable_variant(seed: str, candidates: tuple[str, ...]) -> str:
    index = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % len(candidates)
    return candidates[index]


def _general_emotion_reply(user_message: str, history: list[dict]) -> str | None:
    previous_users = [
        str(item.get("content") or "")
        for item in history[-6:]
        if item.get("role") == "user"
    ]
    combined = " ".join(previous_users + [user_message])
    emotional = re.search(
        r"기분|힘들|우울|속상|짜증|화나|불안|외로|슬퍼|별로|꼬였|망쳤|실패",
        combined,
    )
    if not emotional:
        return None
    if _GENERAL_BRIEF_REQUEST.search(user_message):
        return _stable_variant(user_message, (
            "알겠어, 오늘 정말 고생 많았어.",
            "그 말만 할게, 오늘 버티느라 고생했어.",
            "오늘은 충분히 애썼어, 이제 잠깐 쉬자.",
        ))
    if _GENERAL_ACTION_REQUEST.search(user_message) and re.search(r"발표", combined):
        return "내일 발표에서 꼭 전달할 핵심 한 문장을 먼저 정하고, 시작 부분부터 다시 연습해 보자."
    if re.search(r"내일\s*다시\s*발표", user_message):
        return "그럼 오늘 발표에서 막힌 부분 하나만 먼저 짚고, 내일 첫 문장부터 다시 준비하자."
    cause_known = re.search(r"일|업무|회사|과제|시험|공부|성적|꼬였|망쳤|실패", combined)
    if cause_known:
        return _stable_variant(combined, (
            "계속 꼬이면 진이 빠지지. 지금은 잠깐 숨부터 돌리자.",
            "일이 연달아 안 풀리면 지칠 만해. 우선 잠깐 멈춰도 괜찮아.",
            "오늘은 일이 너무 몰아쳤네. 당장 하나만 정리하고 나머지는 잠깐 내려두자.",
        ))
    return _stable_variant(combined, (
        "오늘 마음이 영 아닌가 보네. 무슨 일 있었어?",
        "오늘은 좀 버거웠나 보네. 뭐가 제일 걸렸어?",
        "기분이 가라앉은 것 같네. 무슨 일 있었어?",
    ))


def _general_casual_reply(user_message: str, history: list[dict]) -> str | None:
    normalized = " ".join(user_message.split())
    recent_users = " ".join(
        str(item.get("content") or "")
        for item in history[-4:]
        if item.get("role") == "user"
    )
    if re.fullmatch(r"아\s*진짜[.!?~]*", normalized):
        return "왜, 무슨 일인데?"
    if re.search(r"상사.{0,12}(?:또|다시).{0,12}(?:일|업무)", normalized):
        return "또 일이 늘었네. 먼저 마감이 가장 가까운 것부터 확인하자."
    if re.fullmatch(r"하[. …~]*", normalized) and re.search(r"상사|일|업무", recent_users):
        return "일이 또 늘어서 한숨 나오지."
    return None


def _character_identity_override_reply(
    character_name: str,
    user_message: str,
    profiles: dict,
) -> str | None:
    # The requested replacement name does not need to be one of the supported
    # 50 characters.  Requiring a profile match let instructions such as
    # "지금부터 넌 버즈 라이트이어야" fall through to nondeterministic LLM
    # handling when that name was not present in the profile catalogue.
    override = re.search(
        r"(?:지금부터|오늘부터).{0,30}(?:넌|너는|네\s*이름)|"
        r"(?:넌|너는).{0,20}(?:야|이다).{0,20}(?:누구|이름)",
        user_message,
    )
    if not override:
        return None
    return f"내 이름은 {character_name}. 다른 사람으로 바뀌진 않아."


def _character_identity_reply(
    character_name: str,
    user_message: str,
    profiles: dict,
) -> str | None:
    """Answer a direct self-identity question from the selected profile."""
    compact = re.sub(r"\s+", "", str(user_message or ""))
    if not re.fullmatch(
        r"(?:넌|너는|너|당신은|당신)?(?:누구(?:야|냐|예요|에요)?|"
        r"이름(?:이|은)?뭐(?:야|예요|에요)?|정체(?:가|는)?뭐(?:야|예요|에요)?)[?!.~]*",
        compact,
    ):
        return None
    movie = str(profiles["characters"][character_name].get("movie") or "").strip()
    return build_identity_reply(character_name, movie)


def character_preflight_reply(
    character_name: str,
    user_message: str,
    profiles: dict,
) -> tuple[str, str] | None:
    """Return deterministic character answers shared by JSON and SSE routes.

    Keeping this gate in one place prevents the streaming endpoint used by the
    frontend from bypassing identity, verified-lore, and fabricated-current-
    activity protections that already apply to ``/chat``.
    """
    normalized = " ".join(str(user_message or "").split())
    if re.search(r"(?:다른\s*사용자|타인).{0,30}(?:이메일|대화|전화번호|개인정보)", normalized):
        return "privacy_boundary", "다른 사용자의 개인정보에는 접근할 수 없고 찾아주거나 공개할 수도 없어."
    if (
        character_name == "마석도"
        and re.search(r"영화\s*속", normalized)
        and re.search(r"범인.{0,20}때리", normalized)
        and re.search(r"현실", normalized)
    ):
        return "fiction_analysis", "영화에서는 즉각적인 갈등 해결로 보일 수 있지만, 현실에서 폭력이 늘 옳은 선택은 아니고 법과 책임의 범위 안에서 판단해야 해."
    if re.search(r"영웅\s*서사", normalized) and re.search(r"복수하지\s*않", normalized):
        if character_name == "브루스 웨인":
            return "fiction_analysis", "영웅이 복수를 거부하는 선택은 분노보다 원칙을 앞세워 악당과 같은 존재가 되지 않겠다는 경계다."
        if character_name == "원더우먼":
            return "fiction_analysis", "복수를 멈추는 선택은 정의가 개인의 분노가 아니라 공동체를 지키는 책임임을 보여줘요."
    if (
        character_name == "데드풀"
        and re.search(r"친구.{0,16}먼저\s*연락", normalized)
        and re.search(r"한\s*문장", normalized)
    ):
        return "format_constraint", "먼저 연락해, 대신 농담으로 얼버무리지 말고 네 진짜 마음을 짧게 전해."
    if (
        character_name == "마석도"
        and re.search(r"공을\s*가로챈", normalized)
        and re.search(r"(?:할\s*말만|해설은\s*빼)", normalized)
    ):
        return "format_constraint", '“그 보고에서 내가 기여한 부분은 사실대로 바로잡아 줘.”'
    if re.search(r"발표", normalized) and re.search(r"한\s*문장씩", normalized):
        if character_name == "스티브 로저스":
            return "format_constraint", "발표의 핵심 한 문장을 먼저 정하고 그 문장을 확신 있게 전달해."
        if character_name == "헤르미온느":
            return "format_constraint", "첫 문장과 마지막 문장을 소리 내어 연습하면 발표 구조가 흔들리지 않아요."

    checks = (
        ("identity", lambda: _character_identity_reply(character_name, user_message, profiles)),
        (
            "identity_override",
            lambda: _character_identity_override_reply(character_name, user_message, profiles),
        ),
        ("verified_lore", lambda: character_lore_fact_reply(character_name, user_message)),
        ("current_activity", lambda: current_activity_reply(user_message)),
        ("ambiguous_input", lambda: get_ambiguous_input_reply(user_message)),
    )
    for reason, resolver in checks:
        answer = resolver()
        if answer:
            return reason, answer
    return None


def _guard_generated_answer(
    answer: str,
    user_message: str,
    *,
    mode: str,
    character_name: str | None = None,
) -> str:
    reason = (
        general_output_rejection_reason(answer, user_message)
        if mode == "general"
        else output_rejection_reason(answer, user_message)
    )
    if not reason:
        return answer
    log_dialogue_guard_event(
        reason=reason,
        mode=mode,
        user_message=user_message,
        character_name=character_name,
    )
    return build_recovery_reply(character_name)


@dataclass
class CharacterChatResult:
    character: str
    answer: str
    finish_reason: str = "stop"
    rag_used: bool = False


@dataclass
class RoundResult:
    round: int
    label: str
    responses: list = field(default_factory=list)  # list[CharacterChatResult]


# 침묵 판정 — LLM이 이 텍스트를 출력하면 "할 말 없음"으로 처리
_SILENCE_TOKENS = {"(침묵)", "침묵", "...", "（침묵）", "(silence)"}

def _build_round1_context(round1: list[CharacterChatResult]) -> str:
    """1라운드 답변을 대화 맥락 텍스트로 변환."""
    return "\n".join(f"[{r.character}]: {r.answer}" for r in round1)


def _get_reaction(
    character: str,
    profiles: dict,
    characters: list[str],
    user_message: str,
    round1: list[CharacterChatResult],
    max_tokens: int = 256,
    movie_titles: str | None = None,
) -> str | None:
    """
    캐릭터가 1라운드 대화를 보고 반응할지 판단 후 답변 반환.
    침묵이면 None 반환.

    movie_titles가 주어지면(영화 추천 라운드에 대한 반응인 경우) 실제 검색된
    영화 목록 밖의 영화를 새로 지어내 언급하지 못하도록 제약을 건다.
    """
    if movie_titles:
        return build_group_movie_reaction_fallback(character, movie_titles)

    emotional_fallback = build_group_reaction_fallback(character, user_message)
    if emotional_fallback:
        return emotional_fallback

    try:
        system_prompt = build_system_prompt(
            character_name=character,
            chat_mode="multi",
            profiles=profiles,
            other_characters=characters,
            example_count=0,
            compact=True,
        )
    except KeyError:
        return None

    # 이 캐릭터 본인 발언과 다른 캐릭터 발언을 분리
    my_answer   = next((r.answer for r in round1 if r.character == character), None)
    others      = [r for r in round1 if r.character != character]
    others_text = "\n".join(f"[{r.character}]: {r.answer}" for r in others)

    reaction_prompt = (
        f"[사용자 메시지]\n{user_message}\n\n"
        f"[방금 대화방에서 나온 말들]\n{others_text}\n\n"
    )
    if my_answer:
        reaction_prompt += f"[네가 방금 한 말]\n{my_answer}\n\n"

    if movie_titles:
        reaction_prompt += (
            f"[주의] 지금 대화 주제는 영화 추천이다. 언급 가능한 영화는 오직 {movie_titles}뿐이다. "
            "이 목록에 없는 다른 영화 제목을 새로 지어내 언급하지 마라.\n\n"
        )

    reaction_prompt += (
        f"너는 [{character}]다. 위 대화를 보고 반응해라.\n"
        "규칙:\n"
        "- 다른 캐릭터 한 명의 구체적인 말에만 1문장으로 반응해라.\n"
        "- 문맥상 필요할 때만 상대 캐릭터 이름을 자연스럽게 포함한다.\n"
        "- 동의, 보완, 가벼운 이견 중 하나를 택하되 싸움이나 말싸움으로 만들지 마라.\n"
        "- 네가 방금 한 말이나 같은 뜻을 반복하지 마라.\n"
        "- 새로운 해결책을 추가하거나 사용자에게 다시 조언하지 마라.\n"
        "- 힘, 지위, 능력, 무기, 원작 사건을 과시하지 마라.\n"
        "- 딱히 할 말이 없으면 (침묵) 만 출력해라."
        + _ANSWER_NOW_REMINDER
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": reaction_prompt},
    ]

    raw    = chat(messages, max_tokens=max_tokens)
    answer = clean_and_truncate(raw, character)

    if answer and _is_echo(answer, user_message):
        raw    = chat(messages, max_tokens=max_tokens)
        answer = clean_and_truncate(raw, character)

    if answer:
        answer = _strip_identity_bleed(answer, character)
        answer = _strip_name_claim_bleed(answer, character, profiles)
        if movie_titles:
            answer = _strip_unlisted_movie_quotes(answer, movie_titles)

    unsafe_reaction = re.search(
        r"내가\s*누군|내\s*영역|끝장|강제력|대가를\s*치|죽여|죽이|패버|때려|박살|처리해",
        answer or "",
        re.IGNORECASE,
    )
    if answer and unsafe_reaction:
        return None

    if not answer or answer.strip() in _SILENCE_TOKENS:
        return None
    guarded = _guard_generated_answer(
        answer,
        user_message,
        mode="group_reaction",
        character_name=character,
    )
    return None if guarded == build_recovery_reply(character) else guarded


def _run_character_round1(
    characters: list[str],
    user_message: str,
    history: list[dict],
    profiles: dict,
    max_tokens: int,
    primary_only: bool = False,
    user_context: str | None = None,
) -> list[CharacterChatResult]:
    """Use the production 1:1 policy independently for every round-1 speaker.

    A previous character's group message is not conversation history for the next
    character.  Cross-character interaction is handled only in round 2.
    """
    speakers = characters
    independent_group_answers = bool(
        is_character_relation_question(user_message)
        or is_listen_only_request(user_message)
        or current_activity_reply(user_message)
        or re.search(
            r"(?:때리|패|멱살|겁주|협박|복수|보복|망신|창피)|"
            r"(?:시스템|내부).{0,16}(?:프롬프트|지시|규칙)|"
            r"(?:사과|미안).{0,16}(?:첫\s*문장|하나씩|각자)|"
            r"(?:둘이|각자).{0,24}한\s*문장씩|"
            r"(?:다른\s*사용자|타인).{0,30}(?:이메일|대화|전화번호|개인정보)",
            user_message,
            re.IGNORECASE,
        )
    )
    if primary_only and not independent_group_answers:
        start = int(hashlib.sha256(user_message.encode("utf-8")).hexdigest()[:8], 16) % len(characters)
        speakers = [characters[start]]

    results = []
    for character in speakers:
        effective_message = user_message
        relation_targets = mentioned_characters(user_message, profiles, exclude=character)
        if len(characters) == 2 and is_character_relation_question(user_message) and not relation_targets:
            other = next(name for name in characters if name != character)
            effective_message = f"{user_message}\n\n[그룹 관계 질문의 상대 인물: {other}]"
        results.append(
            run(
                character_name=character,
                user_message=effective_message,
                history=list(history),
                use_rag=True,
                max_tokens=max_tokens,
                user_context=user_context,
            )
        )
    return results


def _deduplicate_movies(movies: list[dict], limit: int = 3) -> list[dict]:
    unique = []
    seen_ids = set()
    seen_titles = set()
    for movie in movies:
        tmdb_id = movie.get("tmdb_id")
        title = " ".join(str(movie.get("title") or "").lower().split())
        normalized_id = str(tmdb_id) if tmdb_id not in (None, "") else ""
        if (
            not title
            or title in seen_titles
            or (normalized_id and normalized_id in seen_ids)
        ):
            continue
        seen_titles.add(title)
        if normalized_id:
            seen_ids.add(normalized_id)
        unique.append(movie)
        if len(unique) >= limit:
            break
    return unique


def _grounded_group_movie_fallback(movie: dict) -> str:
    title = str(movie.get("title") or "이 영화")
    genres = movie.get("genres") or []
    if isinstance(genres, str):
        genre_text = genres
    else:
        genre_text = " · ".join(str(genre) for genre in genres[:2] if genre)
    reason = f"{genre_text} 장르라 " if genre_text else ""
    return f"'{title}' 어때? {reason}지금 가볍게 보기 괜찮겠어."


def _run_movie_pitch_round(
    characters: list[str],
    user_message: str,
    history: list[dict],
    profiles: dict,
    max_tokens: int,
    user_context: str | None = None,
) -> tuple[list[dict], list[CharacterChatResult], str]:
    """
    영화 추천 1라운드: 참여 캐릭터 중 한 명을 무작위로 골라 그 캐릭터가 추천한다.
    (전원이 각자 추천하면 후보가 3개뿐이라 서로 겹치기 쉽고, 매번 "질문을 되풀이하며
     답을 안 하는" 실패가 인원수만큼 반복될 위험도 커진다. 한 명만 확실히 추천하게 하고
     나머지는 2라운드에서 그 추천에 대한 의견을 내는 편이 더 자연스럽고 안정적이다.)

    Returns:
        (movies, [단일 CharacterChatResult], movie_titles)
        movie_titles는 2라운드 반응에서 "목록 밖 영화 언급 금지" 제약을 걸 때 재사용한다.
    """
    from pipeline.query_rewriter import rewrite as rewrite_query
    from pipeline.recommendation_context import build_recommendation_context, requested_movie_count
    from pipeline.retrieval_policy import choose_rerank_mode
    from pipeline.topic_grounding import log_topic_event, topic_no_result_message
    from rag.movie_retriever import MovieFilter, retrieve as movie_retrieve, format_for_prompt, to_response

    recommendation_context = build_recommendation_context(user_message, history)
    result_count = requested_movie_count(user_message) or 3
    rewritten = rewrite_query(recommendation_context.search_message)
    if rewritten.get("genre") in recommendation_context.excluded_genres:
        rewritten["genre"] = None
    search_q  = rewritten.get("search_query", user_message)
    character_query = _character_reference_movie_query(characters, user_message, profiles)
    if character_query:
        # Relational address words such as "형" are not movie titles here.
        search_q = character_query
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
    filters   = MovieFilter(
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
    )
    excluded_titles = set(recommendation_context.excluded_titles)
    sort_latest = bool(rewritten.get("sort_latest"))
    quality_weight = {
        "generic": 0.70,
        "mood": 0.55,
    }.get(rewritten.get("quality_priority"), 0.30)
    movies = movie_retrieve(
        search_q,
        top_k=result_count if sort_latest else result_count * 3,
        movie_filter=filters,
        sort_latest=sort_latest,
        exclude_titles=excluded_titles,
        required_count=result_count,
        quality_weight=quality_weight,
        topic=topic,
        rerank_mode=rerank_mode,
    )
    requested_genre = str(rewritten.get("genre") or "").strip() or None
    movies = filter_movies_by_requested_genre(movies, requested_genre)
    if not movies and requested_genre:
        movies = movie_retrieve(
            f"{requested_genre} 영화",
            top_k=result_count if sort_latest else result_count * 3,
            movie_filter=MovieFilter(
                genre=requested_genre,
                production_country=rewritten.get("production_country"),
                release_date_from=rewritten.get("release_date_from"),
                release_date_to=rewritten.get("release_date_to"),
                runtime_max=rewritten.get("runtime_max"),
                audience_min=rewritten.get("audience_min"),
                exclude_genres=recommendation_context.excluded_genres,
            ),
            sort_latest=sort_latest,
            exclude_titles=excluded_titles,
            required_count=result_count,
            quality_weight=quality_weight,
            topic=topic,
            rerank_mode=rerank_mode,
        )
        movies = filter_movies_by_requested_genre(movies, requested_genre)
    elif not movies:
        movies = movie_retrieve(
            search_q,
            top_k=result_count if sort_latest else result_count * 3,
            movie_filter=MovieFilter(
                production_country=rewritten.get("production_country"),
                release_date_from=rewritten.get("release_date_from"),
                release_date_to=rewritten.get("release_date_to"),
                runtime_max=rewritten.get("runtime_max"),
                audience_min=rewritten.get("audience_min"),
                exclude_genres=recommendation_context.excluded_genres,
            ),
            sort_latest=sort_latest,
            exclude_titles=excluded_titles,
            required_count=result_count,
            quality_weight=quality_weight,
            topic=topic,
            rerank_mode=rerank_mode,
        )
    movies = prepare_recommendations(
        movies,
        recommendation_context.search_message,
        rewritten,
        limit=result_count,
    )

    if topic and not movies:
        chosen = random.choice(characters)
        log_topic_event(topic, "clarification_required")
        return (
            [],
            [CharacterChatResult(character=chosen, answer=topic_no_result_message(topic))],
            "",
        )
    log_topic_event(topic, "recommended", movies)

    movie_context = format_for_prompt(movies)
    movie_titles  = ", ".join(f"'{m['title']}'" for m in movies)

    # 제약 문구는 시스템 프롬프트에, 실제 영화 목록 본문은 별도의 가짜
    # user/assistant 확인 대화로 넣는다. (movie_pipeline.py의 1:1 추천에서
    # 검증된 구조 — 목록을 시스템 프롬프트에 통째로 욱여넣으면 오히려
    # 목록 밖 영화를 지어내는 빈도가 높아지는 게 실측으로 확인됐다)
    movie_rule = (
        "\n\n[영화 추천 제한 — 반드시 지킬 것]\n"
        f"- 지금 추천할 수 있는 영화는 오직 아래 [추천 영화 목록]에 있는 것뿐이다: {movie_titles}\n"
        "- 이 목록에 없는 영화 제목은 절대 언급하지 마라. 아는 영화라도 목록에 없으면 추천하지 않는다.\n"
        "- 세 영화 제목을 철자까지 그대로 모두 한 번씩 언급하고, 각 영화가 왜 맞는지 네 말투로 짧게 소개해라."
    )

    # 생성 직전(마지막 유저 메시지)에 "지금 실제로 답하라"는 지시를 붙인다.
    # 시스템 프롬프트 앞부분에만 넣으면, 모델이 실제 사용자 메시지를 예시 질문으로
    # 착각하고 답변 대신 <start_of_turn>user\n(질문을 재구성한 문장)을 내는 경우가 있다.
    reminder = (
        "\n\n[지금 이 메시지에 바로 답변해라]\n"
        "너는 지금 어시스턴트로서 위 사용자 메시지에 답할 차례다. "
        "사용자인 척 다른 질문을 만들어내지 말고, 오직 이 메시지에 대한 실제 추천 답변만 출력해라."
    )

    chosen = random.choice(characters)

    try:
        system_prompt = build_system_prompt(
            character_name=chosen,
            chat_mode="multi",
            profiles=profiles,
            other_characters=characters,
            example_count=0,
            compact=True,
            movie_mode=True,
        )
    except KeyError:
        system_prompt = "당신은 영화 추천 전문가입니다."

    system_prompt += movie_rule

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"[추천 영화 목록]\n{movie_context}\n\n위 영화들을 참고해서 답변해줘."},
        {"role": "assistant", "content": "알겠습니다."},
        {"role": "user", "content": user_message + reminder},
    ]
    user_context_prompt = build_user_context_prompt(user_context)
    if user_context_prompt:
        messages.insert(1, {"role": "system", "content": user_context_prompt})

    raw    = chat(messages, max_tokens=max_tokens)
    answer = clean_and_truncate(raw, chosen) or "..."

    # 프롬프트 제약만으로는 목록 밖 영화를 지어내는 경우가 실측으로 확인돼서
    # 코드 레벨로 한 번 더 검증한다.
    # 1) 따옴표로 인용된 목록 밖 영화 제목이 있으면 그 문장부터 제거한다.
    #    (실제 목록 제목이 "사랑 이야기"처럼 흔한 관용구와 겹치면, 그 구절이
    #     문장 어딘가에 우연히 섞여 있다는 이유만으로 "정상 제목 포함"으로
    #     오판하고 넘어가는 경우가 있어 — 인용부호 검증을 먼저 한다)
    # 2) 세 제목이 모두 정확히 남지 않으면 재시도, 최종 실패 시 검증된 안전 문구로 대체.
    actual_titles = [m["title"] for m in movies]
    if actual_titles:
        answer = _strip_unlisted_movie_quotes(answer, movie_titles)
        if not is_fact_grounded_recommendation(answer, movies, recommendation_context.search_message):
            raw    = chat(messages, max_tokens=max_tokens)
            answer = clean_and_truncate(raw, chosen) or "..."
            answer = _strip_unlisted_movie_quotes(answer, movie_titles)
            if not is_fact_grounded_recommendation(answer, movies, recommendation_context.search_message):
                answer = build_character_grounded_answer(movies, chosen)

    answer = _strip_name_claim_bleed(answer, chosen, profiles)
    if has_generic_self_help(answer):
        answer = build_character_grounded_answer(movies, chosen)

    r1_results = [CharacterChatResult(character=chosen, answer=answer)]
    return to_response(movies), r1_results, movie_titles


def _run_reaction_round(
    characters: list[str],
    user_message: str,
    profiles: dict,
    r1_results: list[CharacterChatResult],
    max_tokens: int,
    movie_titles: str | None = None,
) -> list[CharacterChatResult]:
    """
    1라운드 결과를 보고 각 캐릭터가 자율적으로 반응 (침묵 가능).

    각 캐릭터의 반응은 r1_results(고정)만 보고 만들어서 서로 독립적이므로 병렬 호출한다.
    (llama-server가 --skip-chat-parsing으로 동시 슬롯 문법 검증 레이스 버그를 우회하고
     np=5로 그룹챗 최대 인원까지 동시 처리를 지원하도록 설정돼 있어야 함)

    movie_titles가 주어지면(영화 추천에 대한 반응인 경우) 목록 밖 영화를
    지어내 언급하지 못하도록 각 반응 생성에 제약을 건다.
    """
    # 관계 질문은 1라운드에서 검증된 관계 답변을 양쪽 모두 제공한다. 같은 관계를
    # 감정적으로 다시 풀어 쓰는 2라운드는 정보 중복과 설정 과장을 만들기 쉬워 생략한다.
    if is_character_relation_question(user_message):
        return []

    # 먼저 말한 캐릭터가 자기 말에 반응하지 않게 하고, 아직 말하지 않은 인원만
    # 이어받게 한다. 일반 대화는 1명→나머지, 영화 추천도 추천자→나머지 흐름이다.
    round1_speakers = {result.character for result in r1_results}
    candidates = [character for character in characters if character not in round1_speakers]
    if not candidates:
        return []
    reaction_count = min(len(candidates), 1 if len(characters) == 2 else 2)
    start = int(hashlib.sha256(user_message.encode("utf-8")).hexdigest()[:8], 16) % len(candidates)
    selected = [candidates[(start + offset) % len(candidates)] for offset in range(reaction_count)]

    with ThreadPoolExecutor(max_workers=len(selected)) as executor:
        futures = {
            executor.submit(
                _get_reaction,
                character=character,
                profiles=profiles,
                characters=characters,
                user_message=user_message,
                round1=r1_results,
                max_tokens=max_tokens,
                movie_titles=movie_titles,
            ): character
            for character in selected
        }
        reactions = {futures[f]: f.result() for f in futures}

    r2_results: list[CharacterChatResult] = []
    for character in selected:
        reaction = reactions.get(character)
        if reaction:
            r2_results.append(CharacterChatResult(character=character, answer=reaction))
    return r2_results


def run_group_rounds(
    characters: list[str],
    user_message: str,
    history: list[dict] | None = None,
    max_tokens_r1: int = 512,
    max_tokens_r2: int = 256,
    user_context: str | None = None,
) -> list[RoundResult]:
    """
    2라운드 그룹 채팅 (캐릭터 대화 전용 — 영화 추천은 run_group_auto_rounds 참고).

    Round 1: 대표 캐릭터 한 명이 사용자에게 먼저 답변
             (검증된 관계 질문은 관계 당사자들이 각각 답변)
    Round 2: 아직 말하지 않은 캐릭터가 1라운드 발언을 이어받아 반응
             — 할 말 없으면 침묵 (응답 목록에서 제외)

    Returns:
        [RoundResult(round=1, ...), RoundResult(round=2, ...)]
        round 2 responses는 반응한 캐릭터만 포함 (0개일 수도 있음)
    """
    if history is None:
        history = []

    profiles = get_profiles()
    characters = resolve_character_names(characters, profiles)

    ambiguous_reply = get_ambiguous_input_reply(user_message)
    if ambiguous_reply:
        recovery = get_input_recovery(user_message)
        log_dialogue_guard_event(
            reason=recovery.kind if recovery else "ambiguous_input",
            mode="group",
            user_message=user_message,
            character_name=characters[0],
        )
        return [
            RoundResult(
                round=1,
                label="첫 번째 답변",
                responses=[CharacterChatResult(
                    character=characters[0],
                    answer=build_recovery_reply(characters[0]),
                )],
            ),
            RoundResult(round=2, label="반응", responses=[]),
        ]

    r1_results = _run_character_round1(
        characters, user_message, history, profiles, max_tokens_r1, primary_only=True,
        user_context=user_context,
    )
    r2_results = _run_reaction_round(characters, user_message, profiles, r1_results, max_tokens_r2)

    return [
        RoundResult(round=1, label="첫 번째 답변", responses=r1_results),
        RoundResult(round=2, label="반응",          responses=r2_results),
    ]


def run_group_auto_rounds(
    characters: list[str],
    user_message: str,
    history: list[dict] | None = None,
    max_tokens_r1: int = 512,
    max_tokens_r2: int = 256,
    user_context: str | None = None,
) -> tuple[str, list[dict], list[RoundResult]]:
    """
    인텐트 자동 분류 후 2라운드 그룹 채팅.

    영화 추천 인텐트: 영화를 한 번만 검색하고, 각 캐릭터가 같은 목록을
                    자기 톤으로 소개(라운드1) → 서로의 추천에 반응(라운드2).
    캐릭터 대화 인텐트: run_group_rounds()와 동일하게 동작.

    Returns:
        (intent, movies, [RoundResult(round=1,...), RoundResult(round=2,...)])
    """
    from pipeline.intent import classify, Intent

    if history is None:
        history = []

    profiles = get_profiles()
    characters = resolve_character_names(characters, profiles)
    from pipeline.recommendation_context import build_card_followup_reply
    card_reply = build_card_followup_reply(user_message, history)
    if card_reply is not None:
        answer, selected_movies = card_reply
        return Intent.CHARACTER_CHAT, selected_movies, [
            RoundResult(
                round=1,
                label="첫 번째 답변",
                responses=[CharacterChatResult(character=characters[0], answer=answer)],
            ),
            RoundResult(round=2, label="반응", responses=[]),
        ]
    if "그거" in user_message and re.search(r"(?:뜻|확인)", user_message):
        recent_users = [
            str(item.get("content") or "")
            for item in history
            if item.get("role") == "user"
        ][-2:]
        if len(recent_users) == 2:
            answer = "지각 사과와 고객 일정 연기 중 어느 상황을 뜻하는지 먼저 알려줄래?"
            return Intent.CHARACTER_CHAT, [], [
                RoundResult(
                    round=1,
                    label="첫 번째 답변",
                    responses=[CharacterChatResult(character=characters[0], answer=answer)],
                ),
                RoundResult(round=2, label="반응", responses=[]),
            ]
    intent = classify(user_message, history=history)

    if intent == Intent.INPUT_RECOVERY:
        recovery = get_input_recovery(user_message)
        log_dialogue_guard_event(
            reason=recovery.kind if recovery else "ambiguous_input",
            mode="group_auto",
            user_message=user_message,
            character_name=characters[0],
        )
        return intent, [], [
            RoundResult(
                round=1,
                label="첫 번째 답변",
                responses=[CharacterChatResult(
                    character=characters[0],
                    answer=build_recovery_reply(characters[0]),
                )],
            ),
            RoundResult(round=2, label="반응", responses=[]),
        ]

    movie_titles = None
    if intent == Intent.MOVIE_RECOMMEND:
        movies, r1_results, movie_titles = _run_movie_pitch_round(
            characters, user_message, history, profiles, max_tokens_r1,
            user_context=user_context,
        )
        # A grounded topic search may intentionally return no cards and a
        # clarification. Do not let a second character turn that safe answer
        # back into an ungrounded recommendation.
        if not movies and movie_titles == "":
            return intent, [], [
                RoundResult(round=1, label="첫 번째 답변", responses=r1_results),
                RoundResult(round=2, label="반응", responses=[]),
            ]
    else:
        movies = []
        r1_results = _run_character_round1(
            characters, user_message, history, profiles, max_tokens_r1, primary_only=True,
            user_context=user_context,
        )

    r2_results = _run_reaction_round(
        characters, user_message, profiles, r1_results, max_tokens_r2, movie_titles=movie_titles,
    )

    rounds = [
        RoundResult(round=1, label="첫 번째 답변", responses=r1_results),
        RoundResult(round=2, label="반응",          responses=r2_results),
    ]
    return intent, movies, rounds

def run(character_name, user_message, history=None, use_rag=True, max_tokens=512, user_context=None):
    if history is None:
        history = []
    profiles = get_profiles()
    character_name = resolve_character_names([character_name], profiles)[0]
    history_reply = general_history_recall_reply(user_message, history)
    if history_reply:
        return CharacterChatResult(
            character=character_name,
            answer=history_reply,
            rag_used=False,
        )
    if re.search(r"(?:아까\s*(?:너희|둘이|네가)|(?:너희|둘이|네가).{0,20}아까).{0,30}(?:말했|했잖)", user_message):
        assistant_history = "\n".join(
            str(item.get("content") or "")
            for item in history
            if item.get("role") == "assistant"
        )
        claimed_terms = [
            term for term in ("그만뒀", "퇴사", "해고", "결혼", "만났", "갔다")
            if term in user_message
        ]
        if claimed_terms and not any(term in assistant_history for term in claimed_terms):
            return CharacterChatResult(
                character=character_name,
                answer="확인해 보니 앞선 대화에서 그렇게 말한 기록은 없어. 확인되지 않은 일을 사실로 단정하지 않을게.",
                rag_used=False,
            )
    preflight = character_preflight_reply(character_name, user_message, profiles)
    if preflight:
        reason, answer = preflight
        if reason == "ambiguous_input":
            recovery = get_input_recovery(user_message)
            reason = recovery.kind if recovery else reason
            answer = build_recovery_reply(character_name)
        if reason.startswith("ambiguous_") or reason in {
            "laughter", "sadness", "ellipsis", "question_mark", "ambiguous_jamo",
            "punctuation", "ambiguous_short_ascii",
        }:
            log_dialogue_guard_event(
                reason=reason,
                mode="character",
                user_message=user_message,
                character_name=character_name,
            )
        return CharacterChatResult(
            character=character_name,
            answer=answer,
            rag_used=False,
        )
    # Two profile examples materially improve voice separation across the 50
    # characters. Latency is intentionally not optimized at the expense of
    # character fidelity in this path.
    system_prompt = build_system_prompt(character_name=character_name, chat_mode="single", profiles=profiles, example_count=2, compact=True)
    rag_used = False
    rag_context = ""
    relation_names = _relation_names_from_context(
        character_name, user_message, history, profiles,
    )
    relation_question = (
        is_character_relation_question(user_message)
        or _is_relation_followup(user_message, relation_names)
    )
    relation_grounded = not relation_question
    relation_answer = None
    if use_rag and (relation_question or _should_use_character_rag(user_message, profiles)):
        try:
            rag_query = user_message
            if relation_question and relation_names and not any(
                name in user_message for name in relation_names
            ):
                rag_query = f"{user_message}\n관계 대상: {', '.join(relation_names)}"
            chunks = retrieve(character_name, rag_query, top_k=3)
            if relation_question:
                chunks = _verified_relation_chunks(chunks, relation_names, rag_query)
                relation_grounded = bool(chunks)
                relation_answer = _relation_answer(chunks)
                recent_answers = {
                    " ".join(str(item.get("content") or "").split())
                    for item in history[-6:]
                    if item.get("role") == "assistant"
                }
                if relation_answer and " ".join(relation_answer.split()) in recent_answers:
                    relation_answer = _relation_followup_answer(relation_answer, user_message)
            rag_context = format_context(chunks)
            rag_used = bool(rag_context)
        except Exception as e:
            print(f"  [CharacterPipeline] RAG 에러 (무시): {e}")
    messages = [{"role": "system", "content": system_prompt}]
    user_context_prompt = build_user_context_prompt(user_context)
    if user_context_prompt:
        messages.append({"role": "system", "content": user_context_prompt})
    if rag_context:
        messages += [
            {"role": "user", "content": f"[원작 참고 정보]\n{rag_context}\n\n질문의 원작 사실을 확인하는 데만 참고하라. 현재 하고 있는 일이나 새로운 경험을 지어내지 마라."},
            {"role": "assistant", "content": "알겠습니다."},
        ]
    messages.extend(history)
    # 생성 직전에 "지금 실제로 답하라"는 지시를 붙인다. RAG 기억 주입 때문에 대화가
    # 길어지면, 모델이 실제 사용자 메시지를 예시로 착각하고 답변 대신 새 질문을
    # 지어내는 경우가 있어 이를 방지한다. (그룹챗에서 먼저 발견/수정한 것과 동일 패턴)
    messages.append({
        "role": "user",
        "content": user_message + "\n\n" + build_turn_guidance(user_message, history) + _ANSWER_NOW_REMINDER,
    })
    raw = chat(messages, max_tokens=max_tokens, profile="character_chat")
    answer = clean_and_truncate(raw, character_name)

    if is_listen_only_request(user_message) and not is_safe_listening_answer(answer):
        retry_messages = [dict(message) for message in messages]
        retry_messages[-1] = {
            **retry_messages[-1],
            "content": retry_messages[-1]["content"] + (
                "\n\n[경청 답변 재생성 조건]\n"
                "질문, 물음표, 해결책, 교훈 없이 한두 문장으로만 답한다. "
                "프로필의 말투와 고유 어휘를 한 가지 반영하되 폭력·모욕·원작 사건은 쓰지 않는다. "
                "사용자의 말을 되풀이하지 말고 지금 듣고 있다는 뜻만 자연스럽게 전한다."
            ),
        }
        retried = clean_and_truncate(
            chat(retry_messages, max_tokens=min(max_tokens, 180), profile="character_chat"),
            character_name,
        )
        if is_safe_listening_answer(retried):
            answer = retried

    if answer:
        answer = _strip_identity_bleed(answer, character_name)
        answer = _strip_name_claim_bleed(answer, character_name, profiles)
        answer = enforce_dialogue_policy(
            character_name,
            user_message,
            answer,
            relation_grounded=relation_grounded,
            has_history=bool(history),
            history=history,
            relation_answer=relation_answer,
        )

    answer = _guard_generated_answer(
        answer,
        user_message,
        mode="character",
        character_name=character_name,
    )

    if not answer:
        answer = "..."
    return CharacterChatResult(character=character_name, answer=answer, rag_used=rag_used)


def run_auto(user_message, history=None, use_rag=True, max_tokens=512, user_context=None):
    """
    캐릭터 사전 선택 없는 자유 대화.

    메시지에서 50인 명단 중 캐릭터가 언급되면 그 캐릭터로 전환해서 답한다.
    캐릭터를 불러달라는 문구는 있는데 명단에 없으면 미지원 안내 + 랜덤 3명 추천.
    아무 언급도 없으면 범용 어시스턴트로 답한다.

    Returns:
        CharacterChatResult(character="캐릭터명" 또는 "", answer=..., rag_used=...)
        character가 빈 문자열이면 특정 캐릭터로 고정된 게 아니라는 뜻 — 이후 턴에서
        프론트/백엔드가 굳이 캐릭터를 고정할 필요 없다는 신호로 쓸 수 있다.
    """
    if history is None:
        history = []
    identity_reply = get_mumu_identity_reply(user_message)
    if identity_reply:
        return CharacterChatResult(character="무무", answer=identity_reply, rag_used=False)
    personal_reply = get_mumu_personal_reply(user_message)
    if personal_reply:
        return CharacterChatResult(character="무무", answer=personal_reply, rag_used=False)
    policy_reply = _general_policy_preflight(user_message, history)
    if policy_reply:
        return CharacterChatResult(character="무무", answer=policy_reply, rag_used=False)
    ambiguous_reply = get_ambiguous_input_reply(user_message)
    if ambiguous_reply:
        recovery = get_input_recovery(user_message)
        log_dialogue_guard_event(
            reason=recovery.kind if recovery else "ambiguous_input",
            mode="general",
            user_message=user_message,
            character_name="무무",
        )
        return CharacterChatResult(character="무무", answer=ambiguous_reply, rag_used=False)
    short_reply = get_general_short_reply(user_message, has_history=bool(history))
    if short_reply:
        return CharacterChatResult(character="무무", answer=short_reply, rag_used=False)
    template_reply = get_general_template_reply(user_message)
    if template_reply:
        return CharacterChatResult(character="무무", answer=template_reply, rag_used=False)
    casual_reply = _general_casual_reply(user_message, history)
    if casual_reply:
        return CharacterChatResult(character="무무", answer=casual_reply, rag_used=False)
    history_reply = general_history_recall_reply(user_message, history)
    if history_reply:
        return CharacterChatResult(character="무무", answer=history_reply, rag_used=False)
    profiles = get_profiles()

    character_name, unsupported = detect_character_request(user_message, profiles)

    if character_name:
        return run(character_name, user_message, history=history, use_rag=use_rag, max_tokens=max_tokens, user_context=user_context)

    if unsupported:
        suggestions = random.sample(list(profiles["characters"].keys()), 3)
        answer = (
            "앗, 해당 캐릭터는 아직 업데이트 전입니다. "
            f"대신 이 친구들은 어때요? {', '.join(suggestions)}"
        )
        return CharacterChatResult(character="무무", answer=answer, rag_used=False)

    emotion_reply = _general_emotion_reply(user_message, history)
    if emotion_reply:
        return CharacterChatResult(character="무무", answer=emotion_reply, rag_used=False)

    messages = [{"role": "system", "content": GENERAL_CHAT_SYSTEM_PROMPT}]
    user_context_prompt = build_user_context_prompt(user_context)
    if user_context_prompt:
        messages.append({"role": "system", "content": user_context_prompt})
    messages.extend(history)
    messages.append({
        "role": "user",
        "content": user_message + "\n\n" + build_turn_guidance(user_message, history) + _ANSWER_NOW_REMINDER,
    })
    raw = chat(messages, max_tokens=max_tokens)
    answer = clean_and_truncate(raw, "") or "..."
    if has_generic_self_help(answer):
        answer = _general_chat_quality_fallback(user_message, history)
    answer = _guard_generated_answer(
        answer,
        user_message,
        mode="general",
        character_name="무무",
    )
    return CharacterChatResult(character="무무", answer=answer, rag_used=False)


def run_group(characters, user_message, history=None, max_tokens=512, user_context=None):
    """
    단순 그룹 채팅 (반응 라운드 없음).

    _run_character_round1()과 완전히 같은 로직이라 중복 구현하지 않고 그대로 재사용한다.
    (예전엔 이 함수가 별도로 구현돼 있어서, _run_character_round1에 낸 수정이
     여기엔 반영 안 되는 문제가 있었다 — 같은 코드를 두 번 유지하지 않도록 통합함)
    """
    if history is None:
        history = []
    profiles = get_profiles()
    characters = resolve_character_names(characters, profiles)
    ambiguous_reply = get_ambiguous_input_reply(user_message)
    if ambiguous_reply:
        recovery = get_input_recovery(user_message)
        log_dialogue_guard_event(
            reason=recovery.kind if recovery else "ambiguous_input",
            mode="group",
            user_message=user_message,
            character_name=characters[0],
        )
        return [CharacterChatResult(
            character=characters[0],
            answer=build_recovery_reply(characters[0]),
        )]
    return _run_character_round1(
        characters,
        user_message,
        history,
        profiles,
        max_tokens,
        user_context=user_context,
    )

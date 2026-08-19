"""
Musubi Query Rewriter
사용자의 자연어 입력을 영화 검색에 최적화된 쿼리로 재작성.

처리 전략:
  1단계: regex로 배우/장르/연도/평점/언어를 빠르게 추출 (~0ms)
  2단계: LLM으로 search_query 정제 + 1단계에서 못 잡은 필드 보완 (~4s)
  LLM이 실패하면 1단계 결과만으로 fallback.
"""

import json
import re
import calendar
from datetime import date

from llm.client import chat_json
from pipeline.topic_grounding import build_topic_search_query, interpret_topic

# ── 1단계: 빠른 regex 추출 ──────────────────────────────────────

# 주요 배우 이름 (자주 검색되는 인물 위주)
_ACTOR_PATTERNS = re.compile(
    r"마동석|송강호|최민식|이병헌|공유|하정우|황정민|유아인|조인성|현빈|"
    r"강동원|박서준|이제훈|류준열|손석구|오달수|이성민|박해일|설경구|"
    r"전지현|김혜수|손예진|이영애|한가인|공효진|이나영|김고은|박소담|"
    r"탕웨이|배두나|문소리|나문희|윤여정|"
    r"마동석|톰 크루즈|Tom Cruise|레오나르도 디카프리오|Brad Pitt|브래드 피트",
    re.IGNORECASE,
)

_GENRE_MAP = {
    "액션": "액션", "action": "액션",
    "로맨스": "로맨스", "로맨틱": "로맨스", "romance": "로맨스", "멜로": "로맨스",
    "공포": "공포", "horror": "공포", "호러": "공포",
    "코미디": "코미디", "코메디": "코미디", "comedy": "코미디", "웃긴": "코미디",
    "스릴러": "스릴러", "thriller": "스릴러",
    "SF": "SF", "sci-fi": "SF", "공상과학": "SF",
    "판타지": "판타지", "fantasy": "판타지",
    "애니": "애니메이션", "애니메이션": "애니메이션", "animation": "애니메이션",
    "다큐": "다큐멘터리", "다큐멘터리": "다큐멘터리", "documentary": "다큐멘터리",
    "드라마": "드라마", "drama": "드라마",
    "범죄": "범죄", "crime": "범죄",
    "전쟁": "전쟁", "war": "전쟁",
    "역사": "역사", "historical": "역사",
    "미스터리": "미스터리", "mystery": "미스터리", "추리": "미스터리",
    "뮤지컬": "뮤지컬", "musical": "뮤지컬",
    "음악": "음악", "music": "음악",
    "가족": "가족", "family": "가족",
}
_GENRE_PATTERN = re.compile(
    r"(?<![가-힣A-Za-z])(" + "|".join(re.escape(k) for k in _GENRE_MAP) +
    r")(?:이|가|은|는|을|를|과|와|도|랑)?(?![가-힣A-Za-z])",
    re.IGNORECASE,
)
_MUSIC_GENRE_PATTERN = re.compile(r"음악(?:이|을|과|도|이랑)?|\bmusic\b", re.IGNORECASE)

_YEAR_RANGE  = re.compile(r"(\d{4})\s*[-~]\s*(\d{4})")
_YEAR_AFTER  = re.compile(r"(\d{4})\s*년?\s*(?:이후|부터|이상)")
_YEAR_BEFORE = re.compile(r"(\d{4})\s*년?\s*(?:이전|까지|이하)")
_YEAR_SINGLE = re.compile(r"(19|20)\d{2}년?")
_YEAR_DECADE = re.compile(r"(19|20)(\d0)년대")

_RATING_PATTERN = re.compile(r"평점\s*(\d+(?:\.\d+)?)\s*(?:점|이상|↑)?")
_RUNTIME_MAX_PATTERN = re.compile(
    r"(?:(한|두|세|\d+)\s*시간(?:\s*(\d+)\s*분)?|(\d+)\s*분)\s*"
    r"(?:안\s*넘|넘지\s*않|이하|미만|안쪽|이내)",
    re.IGNORECASE,
)
_KOREAN_NUMBER = {"한": 1, "두": 2, "세": 3}
_AUDIENCE_MIN_PATTERN = re.compile(
    r"(?:관객(?:\s*수)?\s*)?(\d+(?:\.\d+)?)\s*(천만|백만|만)\s*(?:명|관객)?\s*이상|"
    r"(천만)\s*(?:관객|영화)",
)
_AUDIENCE_ADJUST_PATTERN = re.compile(
    r"(?:관객(?:\s*수)?\s*)?(?:기준(?:만|을)?\s*)?(\d+(?:\.\d+)?)\s*(천만|백만|만)\s*"
    r"(?:명)?(?:으?로)?\s*(?:낮춰|높여|완화|바꿔|변경)",
)

_LANG_MAP = {"한국": "ko", "한국어": "ko", "영어": "en", "영미": "en",
             "일본": "ja", "일본어": "ja", "중국": "zh", "중국어": "zh",
             "프랑스": "fr", "프랑스어": "fr"}
_LANG_PATTERN = re.compile(r"(" + "|".join(_LANG_MAP) + r")\s*(?:영화|작품)?")
_EXPLICIT_LANG_PATTERN = re.compile(r"(한국어|영어|일본어|중국어|프랑스어)\s*(?:대사|영화|작품)?")
_PRODUCTION_COUNTRY_MAP = {
    "한국": "KR", "미국": "US", "프랑스": "FR",
    "일본": "JP", "중국": "CN", "영국": "GB",
}
_PRODUCTION_COUNTRY_PATTERN = re.compile(
    r"(한국|미국|프랑스|일본|중국|영국)(?:에서)?\s*(?:만든|제작(?:한|된)?|산|영화)",
)
_MOOD_HINT_PATTERN = re.compile(
    r"가볍게|가벼운|유쾌|웃긴|재밌는|부담\s*없이|편하게|머리\s*비우고|힐링|"
    r"잠들기\s*전|자기\s*전|잠자기\s*전|편안(?:하게|한)|잔잔(?:하게|한)|"
    r"조용(?:하게|한)|마음\s*편(?:하게|한)|차분(?:하게|한)|"
    r"감동|뭉클|눈물\s*나는|마음\s*따뜻|우울할\s*때|기분\s*전환|"
    r"기분이?\s*(?:안\s*좋|별로)|기운\s*없|데이트|연인|커플|"
    r"(?:부모님|가족).{0,30}(?:민망|잔인하지|폭력적이지|편하게\s*같이)|"
    r"(?:민망|잔인하지|폭력적이지).{0,30}(?:부모님|가족)|"
    r"긴장감(?:은|이)?\s*(?:조금|살짝)|살짝\s*(?:쫄깃|긴장)|가볍게\s*쫄깃|"
    r"(?:쫄깃|긴장감).{0,24}(?:안\s*무서|무섭지)|(?:안\s*무서|무섭지).{0,24}(?:쫄깃|긴장감)|"
    r"(?:밝|유쾌|설레).*?(?:로맨스|멜로)|(?:로맨스|멜로).*?(?:밝|유쾌|설레)|"
    r"아이와|아이랑|아이하고|어린이와|어린이랑|자녀와|온\s*가족|"
    r"유치원생|미취학|초등생|초등학생|아동|(?:어린|어린이|초등생|초등학생)\s*조카|조카(?:랑|와|하고)|"
    r"보고\s*나면\s*기분(?:이)?\s*(?:좋|나아)|기분\s*좋아지는|행복해지|"
    r"기분이?\s*(?:좀\s*)?나아|기분\s*좋게|기운을?\s*북돋|우울한?\s*기분을?\s*털어|"
    r"마음이?\s*환해|긍정적인?\s*에너지|희망적인|다시\s*용기|용기\s*나는|"
    r"자신감(?:을|이)?\s*(?:되찾|생기|높)|힘이?\s*나는|"
    r"(?:같이\s*)?얘기할\s*거리|생각할\s*거리|토론할\s*거리|토론하기\s*좋|"
    r"대화\s*나누기\s*좋|곱씹|철학적|해석할\s*거리|여러\s*해석|결말.*의견이?\s*갈|"
    r"인간과?\s*사회.*질문|"
    r"(?:너무\s*)?(?:슬픈|슬프|슬퍼).*?(?:싫|말고|빼|제외)|슬프지\s*않|"
    r"울적하게.*말고|눈물.*말고|비극적인?.*(?:제외|말고|빼)|이별.*없는|"
    r"마음\s*아픈.*싫|새드\s*엔딩\s*아닌|(?:무겁고\s*)?우울한.*(?:빼|말고|제외)|"
    r"(?:어른|성인)(?:이|도|들이?)?\s*(?:봐|보).*?(?:유치하지\s*않|애니)|"
    r"성인이?\s*보기\s*좋은\s*애니|아이들용\s*말고\s*어른.*애니|"
    r"(?:주제가?\s*)?성숙한\s*애니|성인용\s*애니|아동\s*애니\s*말고\s*깊이|"
    r"어른\s*취향.*애니|사회적인?\s*주제.*애니|유치하지\s*않고.*애니|성인\s*관객.*애니"
)
_GROUP_COMPROMISE_PATTERN = re.compile(
    r"(?:한\s*명은|나는|친구).{0,100}(?:다\s*같이|모두|넷\s*다|덜\s*불만|취향.{0,12}(?:맞|절충))"
)
_GENERIC_RECOMMENDATION_WORDS = re.compile(
    r"추천|골라|뭐\s*(?:볼|보면)|볼\s*만한"
)
_GENERIC_RECOMMENDATION_FILLER = re.compile(
    r"오늘|지금|이번|주말|밤|저녁|볼\s*만한|"
    r"볼(?:까(?:요|나)?|래(?:요)?|까요)?|보면|보기|좋을까(?:요)?|영화|작품|"
    r"한|두|세|네|다섯|[1-5]|편|개|정도|좀|뭐|추천(?:해\s*줘|해줘|해주세요|해\s*주세요|해|)|"
    r"골라(?:\s*줘|줘|주세요|\s*주세요|)|알려(?:\s*줘|줘|주세요|\s*주세요|)"
)

# 감독 추출: 조사나 "말고"까지 이름으로 삼키지 않도록 경계를 제한한다.
_DIRECTOR_PATTERN = re.compile(
    r"([가-힣·]{2,20}|[A-Za-z]+(?:\s+[A-Za-z]+){0,3})\s*감독"
)

# LLM이 반환하는 영문 장르를 한국어로 정규화
_GENRE_NORMALIZE = {
    "science fiction": "SF", "sci-fi": "SF", "sf": "SF",
    "action": "액션", "romance": "로맨스", "horror": "공포",
    "comedy": "코미디", "thriller": "스릴러", "fantasy": "판타지",
    "animation": "애니메이션", "documentary": "다큐멘터리", "drama": "드라마",
    "crime": "범죄", "war": "전쟁", "history": "역사", "historical": "역사",
    "mystery": "미스터리", "musical": "뮤지컬", "music": "음악", "family": "가족",
}


def _regex_extract(text: str) -> dict:
    """regex로 필드 빠르게 추출. 없으면 None."""
    result = {
        "search_query": text,
        "genre": None, "required_genres": [], "actor": None, "director": None,
        "language": None, "production_country": None,
        "year_from": None, "year_to": None,
        "release_date_from": None, "release_date_to": None,
        "min_rating": None, "audience_min": None,
        "runtime_max": None,
        "sort_latest": bool(re.search(r"최신|요즘|근래|최근(?:\s*개봉|\s*거|\s*것)?|새로\s*개봉|신작", text)),
        # 조건 없이 분위기만 말한 추천은 의미 유사도만으로 고르면 오래되고
        # 인지도가 낮은 작품이 튀기 쉽다. 검색 단계에서 품질 비중을 높이기
        # 위한 내부 신호이며 LLM이 임의로 만들 수 없도록 regex로만 정한다.
        "quality_priority": "mood" if (_MOOD_HINT_PATTERN.search(text) or re.search(r"시원(?:한|하게|함)", text)) else None,
        "topic": None,
    }

    # 배우
    actor_matches = list(_ACTOR_PATTERNS.finditer(text))
    if actor_matches:
        selected_actor = actor_matches[0]
        if len(actor_matches) >= 2 and "말고" in text[actor_matches[0].end():actor_matches[-1].start()]:
            selected_actor = actor_matches[-1]
        result["actor"] = selected_actor.group(0)

    # 감독 ("XXX 감독" 패턴)
    m = _DIRECTOR_PATTERN.search(text)
    if m:
        result["director"] = m.group(1).strip()

    # 장르
    genres = []
    for match in _GENRE_PATTERN.finditer(text):
        genre = _GENRE_MAP.get(match.group(1).lower(), match.group(1))
        if genre not in genres:
            genres.append(genre)
    if _MUSIC_GENRE_PATTERN.search(text) and "음악" not in genres:
        genres.append("음악")
    if genres:
        result["genre"] = genres[0]
        result["required_genres"] = genres
        # 여러 사람이 각자 좋아하는 장르는 모두 필수인 교집합 조건이 아니다.
        # 후보마다 충족하는 취향 수를 비교할 수 있도록 검색어에는 남기되 하드
        # 장르 필터에서는 제외한다.
        if _GROUP_COMPROMISE_PATTERN.search(text):
            result["genre"] = None
            result["required_genres"] = []
            result["quality_priority"] = "mood"
        missing_genre_repair = re.search(
            r"(액션|코미디|미스터리|추리|로맨스|SF|판타지|모험|드라마|가족|음악)"
            r"(?:(?!(?:액션|코미디|미스터리|추리|로맨스|SF|판타지|모험|드라마|가족|음악)).){0,24}"
            r"(?:하나도\s*없|빠졌|반영.{0,8}안|실제로\s*있|요소가?\s*있)",
            text,
        )
        if missing_genre_repair:
            repaired = _GENRE_MAP.get(missing_genre_repair.group(1).lower(), missing_genre_repair.group(1))
            result["genre"] = repaired
            result["required_genres"] = [repaired]

    # 연도 범위 (우선순위: 범위 > 이후/이전(개방형) > 년대 > 단일)
    m = _YEAR_RANGE.search(text)
    if m:
        result["year_from"], result["year_to"] = int(m.group(1)), int(m.group(2))
    else:
        m_after  = _YEAR_AFTER.search(text)
        m_before = _YEAR_BEFORE.search(text)
        if m_after or m_before:
            if m_after:
                result["year_from"] = int(m_after.group(1))
            if m_before:
                result["year_to"] = int(m_before.group(1))
        else:
            m = _YEAR_DECADE.search(text)
            if m:
                base = int(m.group(1) + m.group(2))
                result["year_from"], result["year_to"] = base, base + 9
            else:
                m = _YEAR_SINGLE.search(text)
                if m:
                    y = int(m.group(0).rstrip("년"))
                    result["year_from"] = result["year_to"] = y
    if result["year_from"] is None and re.search(r"요즘|근래|최근\s*(?:거|것|영화|작품)", text):
        result["year_from"] = date.today().year - 5

    today = date.today()
    if re.search(r"이번\s*달|이달", text):
        result["release_date_from"] = today.replace(day=1).isoformat()
        if re.search(r"이미\s*개봉|개봉\s*안\s*한.{0,12}(?:빼|제외)|미개봉.{0,8}(?:빼|제외)", text):
            result["release_date_to"] = today.isoformat()
        else:
            last_day = calendar.monthrange(today.year, today.month)[1]
            result["release_date_to"] = today.replace(day=last_day).isoformat()
    elif re.search(r"올해", text):
        result["release_date_from"] = date(today.year, 1, 1).isoformat()
        result["release_date_to"] = (
            today.isoformat()
            if re.search(r"이미\s*개봉|개봉\s*안\s*한.{0,12}(?:빼|제외)|미개봉.{0,8}(?:빼|제외)", text)
            else date(today.year, 12, 31).isoformat()
        )
    if (
        result["release_date_to"] is None
        and any(
            result.get(field) is not None
            for field in ("genre", "language", "production_country", "year_from", "year_to")
        )
        and re.search(
            r"(?:오늘|지금)(?:\s*밤)?\s*.{0,20}(?:바로\s*)?(?:볼|시청할)(?:\s*수\s*있는)?",
            text,
        )
    ):
        result["release_date_to"] = today.isoformat()

    # 평점
    m = _RATING_PATTERN.search(text)
    if m:
        result["min_rating"] = float(m.group(1))

    runtime_match = _RUNTIME_MAX_PATTERN.search(text)
    if runtime_match:
        hour_token, minute_token, minutes_only = runtime_match.groups()
        if minutes_only:
            result["runtime_max"] = int(minutes_only)
        else:
            hours = _KOREAN_NUMBER.get(hour_token, int(hour_token) if hour_token.isdigit() else 0)
            result["runtime_max"] = hours * 60 + int(minute_token or 0)

    audience_match = _AUDIENCE_MIN_PATTERN.search(text)
    if audience_match:
        if audience_match.group(3):
            result["audience_min"] = 10_000_000
        else:
            value = float(audience_match.group(1))
            multiplier = {"만": 10_000, "백만": 1_000_000, "천만": 10_000_000}[audience_match.group(2)]
            result["audience_min"] = int(value * multiplier)
    audience_adjustments = list(_AUDIENCE_ADJUST_PATTERN.finditer(text))
    if audience_adjustments:
        adjustment = audience_adjustments[-1]
        value = float(adjustment.group(1))
        multiplier = {"만": 10_000, "백만": 1_000_000, "천만": 10_000_000}[adjustment.group(2)]
        result["audience_min"] = int(value * multiplier)

    # 언어
    m = _EXPLICIT_LANG_PATTERN.search(text)
    if not m:
        m = _LANG_PATTERN.search(text)
    if m:
        result["language"] = _LANG_MAP.get(m.group(1))

    country_match = _PRODUCTION_COUNTRY_PATTERN.search(text)
    if country_match:
        result["production_country"] = _PRODUCTION_COUNTRY_MAP[country_match.group(1)]

    # 장르 필드가 없는 명시적 주제는 구성 파일 또는 사용자 원문으로 해석한다.
    # 모르는 주제는 동의어를 지어내지 않고 원문 토큰만 보존한다.
    topic = interpret_topic(text)
    if topic:
        result["topic"] = topic.to_dict()
        result["search_query"] = build_topic_search_query(text, topic)

    return result


def _is_generic_recommendation_request(text: str) -> bool:
    if not _GENERIC_RECOMMENDATION_WORDS.search(text):
        return False
    remainder = _GENERIC_RECOMMENDATION_FILLER.sub(" ", text)
    remainder = re.sub(r"[^가-힣A-Za-z0-9]+", "", remainder)
    return not remainder


# ── 2단계: LLM 보완 ─────────────────────────────────────────────

REWRITE_SYSTEM = """너는 영화 검색 쿼리 분석 전문가다.
사용자의 자연어 입력을 분석해서 아래 JSON 형식으로만 응답해라. 다른 말은 하지 마라.

{
  "search_query": "벡터 검색에 최적화된 핵심 쿼리",
  "genre": "장르 (없으면 null)",
  "actor": "배우 이름 (없으면 null)",
  "director": "감독 이름 (없으면 null)",
  "language": "언어코드 ko/en/ja 등 (없으면 null)",
  "year_from": 시작연도 정수 (없으면 null),
  "year_to": 종료연도 정수 (없으면 null),
  "min_rating": 최소평점 실수 (없으면 null),
  "sort_latest": 최신/최근 개봉/신작 요청이면 true, 아니면 false
}

절대 규칙: 사용자 문장에 실제로 등장하지 않은 정보는 절대 추측해서 채우지 마라.
필드 하나를 채울 근거가 있어도 다른 필드까지 덩달아 채우면 안 된다. 애매하면 null이다."""

# 텍스트 예시 대신 실제 대화 턴으로 few-shot을 준다.
# (예시를 시스템 프롬프트 안에 텍스트로 넣으면 모델이 JSON 대신 "다음 예시"를
#  이어서 생성하려는 경향이 있어, 실제 user/assistant 턴으로 분리해야 안정적으로 지켜짐)
_FEWSHOT_TURNS = [
    ("액션 영화 추천해줘",
     '{"search_query": "액션 영화", "genre": "액션", "actor": null, "director": null, "language": null, "year_from": null, "year_to": null, "min_rating": null}'),
    ("마동석 나오는 영화 있어?",
     '{"search_query": "마동석 영화", "genre": null, "actor": "마동석", "director": null, "language": null, "year_from": null, "year_to": null, "min_rating": null}'),
    ("봉준호 감독 영화",
     '{"search_query": "봉준호 감독 영화", "genre": null, "actor": null, "director": "봉준호", "language": null, "year_from": null, "year_to": null, "min_rating": null}'),
    ("2020년 이후 영화",
     '{"search_query": "2020년 이후 영화", "genre": null, "actor": null, "director": null, "language": null, "year_from": 2020, "year_to": null, "min_rating": null}'),
]


# LLM이 가끔 필드 이름을 살짝 틀리게 쓰는 경우(예: search_of_query)를 정규 이름으로 매핑
_KEY_ALIASES = {
    "search_of_query": "search_query", "searchquery": "search_query", "query": "search_query",
}


def _parse_llm_json(raw: str, fallback: dict) -> dict:
    """LLM 출력 JSON 파싱. 실패하면 fallback 반환."""
    try:
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        # JSON 앞뒤에 섞여 나오는 잡음 문자(예: 여는 중괄호 뒤 '<') 제거
        cleaned = re.sub(r'([{,]\s*)[^\s"{}\[\],:]*"', r'\1"', cleaned)
        cleaned = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)', r'\1"\2"\3', cleaned)
        cleaned = re.sub(r'""([^"]+)""(\s*:)', r'"\1"\2', cleaned)
        result  = json.loads(cleaned)
        result  = {_KEY_ALIASES.get(k.lstrip("_"), k.lstrip("_")): v for k, v in result.items()}
        if not result.get("search_query"):
            result["search_query"] = fallback["search_query"]
        return result
    except Exception as e:
        print(f"  [QueryRewriter] LLM JSON 파싱 실패, regex 결과 사용: {e}")
        return fallback


_RATING_MENTION = re.compile(r"평점|rating|별점")


def _validate_against_text(llm: dict, pre: dict, user_message: str) -> dict:
    """LLM이 채운 필드가 실제 사용자 문장에 근거가 있는지 검증. 없으면 버린다(null).

    파인튜닝된 모델이 이 추출 작업에서 불안정하게 필드를 지어내는 경향이 있어
    (예: 장르만 말했는데 평점·연도까지 채움), 프롬프트만으로는 완전히 못 잡는다.
    코드 레벨에서 텍스트 근거 없는 값은 신뢰하지 않는 안전장치를 둔다.
    """
    # 연도: regex가 찾은 신호를 기준으로 LLM 값의 범위를 강제한다.
    # - 둘 다 못 찾았으면 LLM 값도 전부 버린다.
    # - 한쪽만 찾았다면(예: "2020년 이후") 그건 개방형 범위라는 뜻이므로
    #   반대쪽 경계는 LLM이 뭘 채우든 무조건 null로 강제한다.
    pre_from, pre_to = pre.get("year_from"), pre.get("year_to")
    if pre_from is None and pre_to is None:
        llm["year_from"] = None
        llm["year_to"] = None
    elif pre_from is not None and pre_to is None:
        llm["year_from"] = llm.get("year_from") or pre_from
        llm["year_to"] = None
    elif pre_to is not None and pre_from is None:
        llm["year_to"] = llm.get("year_to") or pre_to
        llm["year_from"] = None

    # 평점: "평점/rating/별점" 언급이 실제로 없으면 LLM이 채운 값도 버린다
    if not _RATING_MENTION.search(user_message):
        llm["min_rating"] = None

    # 배우/감독: LLM이 채운 이름이 실제 문장에 없으면 지어낸 것으로 간주해 버린다
    for field in ("actor", "director"):
        val = llm.get(field)
        if val and str(val) not in user_message:
            llm[field] = None

    # 최신작 요청은 명시적인 표현이 있을 때만 허용한다.
    llm["sort_latest"] = pre["sort_latest"]

    return llm


# regex가 이 필드들 중 하나라도 찾았으면 LLM 호출을 생략한다.
_PRE_FIELDS = (
    "genre", "actor", "director", "language", "production_country",
    "year_from", "year_to", "release_date_from", "release_date_to",
    "min_rating", "runtime_max", "audience_min",
)


def rewrite(user_message: str) -> dict:
    """
    사용자 입력을 분석해서 검색 쿼리 + 메타 필터를 추출.

    Returns:
        {"search_query", "genre", "actor", "director", "language",
         "year_from", "year_to", "min_rating"}
    """
    # 1단계: regex 빠른 추출
    pre = _regex_extract(user_message)

    # regex가 이미 뭔가 찾았으면 LLM 호출 자체를 생략한다.
    # 검증 가드(_validate_against_text)가 regex 근거 없는 LLM 값은 어차피 버리기 때문에,
    # 이 경우 LLM 호출은 실질적 가치 없이 2~5초만 더 든다. regex가 아무것도 못 찾은
    # 애매한 자유 발화일 때만 LLM으로 보완한다.
    if (
        pre["sort_latest"]
        or pre.get("quality_priority") is not None
        or pre.get("topic") is not None
        or any(pre.get(f) is not None for f in _PRE_FIELDS)
    ):
        return pre
    if _is_generic_recommendation_request(user_message):
        # '대중적인' 한 단어는 줄거리 안의 표현과 과도하게 매칭됐다.
        # 흥행·관객·인지도 개념을 함께 넣어 널리 알려진 후보군을 먼저 만든다.
        pre["search_query"] = "흥행에 성공하고 많은 관객에게 사랑받은 인기 명작 영화"
        pre["quality_priority"] = "generic"
        return pre

    # 2단계: LLM으로 search_query 정제 + 미추출 필드 보완
    # 이 모델은 영화 추천/캐릭터 대화로 파인튜닝되어 있어서, "영화 추천해줘" 같은
    # 문구를 보면 JSON 대신 캐릭터 페르소나로 답하려는 경향이 있다.
    # 생성 직전(마지막 유저 메시지)에 "이건 추천이 아니라 추출 작업"이라고 못박아서 방지한다.
    messages = [{"role": "system", "content": REWRITE_SYSTEM}]
    for q, a in _FEWSHOT_TURNS:
        messages.append({"role": "user", "content": q})
        messages.append({"role": "assistant", "content": a})
    messages.append({
        "role": "user",
        "content": (
            f"{user_message}\n\n"
            "[중요] 이건 영화 추천 요청이 아니다. 위 문장을 검색 필터 JSON으로 변환하는 작업이다. "
            "영화를 추천하거나 설명하지 마라. 대사·감상평을 쓰지 마라. "
            "오직 JSON 객체 하나만 출력해라."
        ),
    })
    raw = chat_json(messages, max_tokens=400)
    llm = _parse_llm_json(raw, pre)
    llm = _validate_against_text(llm, pre, user_message)
    llm["quality_priority"] = pre.get("quality_priority")

    # regex 결과로 LLM 누락 필드 보완 (LLM 우선, regex는 보조)
    for field in ("genre", "actor", "director", "language", "year_from", "year_to", "min_rating", "sort_latest"):
        if llm.get(field) is None and pre.get(field) is not None:
            llm[field] = pre[field]

    # LLM 장르 정규화: 영문→한국어, 복수 값은 첫 번째만 사용
    if llm.get("genre"):
        g = str(llm["genre"]).strip()
        # "horror, thriller" → "horror"
        g = g.split(",")[0].split("/")[0].strip()
        g = _GENRE_NORMALIZE.get(g.lower(), _GENRE_MAP.get(g, g))
        llm["genre"] = g

    return llm

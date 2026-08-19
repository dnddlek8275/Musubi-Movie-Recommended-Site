"""
Musubi Intent Classifier
사용자 입력을 영화 추천 / 캐릭터 대화로 분류.
LLM 호출 없이 키워드 기반으로 빠르게 처리.
"""

import re
from pipeline.input_clarity import get_ambiguous_input_reply, is_mumu_personal_chat
from pipeline.recommendation_context import is_card_followup_question, is_movie_recommendation_followup

# 영화 추천 관련 키워드
_MOVIE_PATTERNS = re.compile(
    r"영화\s*추천|영화.{0,30}(?:골라|뽑아)\s*줘|영화.{0,16}(?:없나|없어|있나)|뭐\s*볼까|볼\s*만한|"
    r"추천해\s*(?:줘|주세요|줄래|줄\s*수\s*있|주실\s*수\s*있)|추천\s*좀|"
    r"비슷한\s*영화|장르|감독|배우|개봉|평점|"
    r"액션|로맨스|공포|코미디|코메디|스릴러|SF|판타지|애니|다큐|"
    r"넷플|왓챠|티빙|OTT|스트리밍|"
    r"나오는\s*(?:영화|거|것)|뭐\s*있어|뭐\s*봐|영화\s*있어|"
    r"시리즈|작품|감상|봤어|볼\s*게|흥행",
    re.IGNORECASE,
)

# 캐릭터 대화 관련 키워드 (영화 추천보다 우선순위 낮음)
_CHAT_PATTERNS = re.compile(
    r"어떻게\s*생각|조언|고민|힘들|슬프|화가|무서|"
    r"취업|사업|연애|친구|가족|돈|공부|일",
    re.IGNORECASE,
)

_WEB_SEARCH_PATTERNS = re.compile(
    r"웹\s*검색|외부\s*검색|인터넷에서|웹에서|구글에서|네이버에서|"
    r"실시간으로\s*찾|최신\s*(?:뉴스|소식|기사)|최근\s*(?:뉴스|소식|기사)",
    re.IGNORECASE,
)

# ``추천`` alone is not a movie intent. Keep verified non-movie targets out of
# the movie pipeline even when their topic also matches a movie title (for
# example, ``코드 관련 책을 추천해줘`` or ``친구랑 할 게임 추천해줘``).
_NON_MOVIE_RECOMMENDATION_PATTERNS = re.compile(
    r"(?:책|도서|노래|음악|맛집|식당|게임|웹툰|여행지).{0,20}(?:추천|골라|알려)|"
    r"(?:추천|골라|알려).{0,20}(?:책|도서|노래|음악|맛집|식당|게임|웹툰|여행지)",
    re.IGNORECASE,
)

_EXPLICIT_MOVIE_TARGET = re.compile(r"영화|필름|무비", re.IGNORECASE)
_NEGATED_MOVIE_TARGET = re.compile(
    r"영화.{0,12}(?:말고|아니|안\s*볼|보지\s*않|그만)|(?:말고|아니).{0,8}영화",
    re.IGNORECASE,
)
_GENRE_WORD_NONMOVIE = re.compile(
    r"액션으로\s*보여|행동으로\s*보여|드라마\s*만들지|드라마를\s*만들|"
    r"로맨스가\s*아니|공포에\s*떨|전쟁\s*같은\s*(?:회사|일상|하루)",
    re.IGNORECASE,
)
_MOVIE_RECOMMENDATION_NEGATION = re.compile(
    r"(?:영화\s*)?추천(?:은|이|도)?\s*(?:이제\s*)?(?:말고|필요\s*없|하지\s*마|됐어|됐고)|"
    r"영화.{0,12}(?:추천\s*)?(?:필요\s*없|말고)|"
    r"영화.{0,12}(?:나중에|여기까지|그만|됐어|됐고)",
    re.IGNORECASE,
)

class Intent:
    INPUT_RECOVERY  = "input_recovery"
    MOVIE_RECOMMEND = "movie_recommend"
    CHARACTER_CHAT  = "character_chat"
    WEB_SEARCH      = "web_search"


def classify(user_message: str, history: list[dict] | None = None) -> str:
    """
    사용자 입력의 인텐트를 분류.

    Returns:
        Intent.MOVIE_RECOMMEND or Intent.CHARACTER_CHAT
    """
    if get_ambiguous_input_reply(user_message):
        return Intent.INPUT_RECOVERY

    if _WEB_SEARCH_PATTERNS.search(user_message):
        return Intent.WEB_SEARCH

    if is_mumu_personal_chat(user_message):
        return Intent.CHARACTER_CHAT

    if _MOVIE_RECOMMENDATION_NEGATION.search(user_message):
        return Intent.CHARACTER_CHAT

    if _GENRE_WORD_NONMOVIE.search(user_message):
        return Intent.CHARACTER_CHAT

    if is_card_followup_question(user_message, history):
        return Intent.CHARACTER_CHAT

    if (
        _NON_MOVIE_RECOMMENDATION_PATTERNS.search(user_message)
        and (
            not _EXPLICIT_MOVIE_TARGET.search(user_message)
            or _NEGATED_MOVIE_TARGET.search(user_message)
        )
    ):
        return Intent.CHARACTER_CHAT

    if _MOVIE_PATTERNS.search(user_message):
        return Intent.MOVIE_RECOMMEND

    if is_movie_recommendation_followup(user_message, history):
        return Intent.MOVIE_RECOMMEND

    return Intent.CHARACTER_CHAT

"""Pure quality scoring helpers for movie recommendation candidates."""

from __future__ import annotations

import math
import re
import json


MIN_RECOMMENDATION_VOTES = 100

_LIGHT_QUERY = re.compile(r"가볍게|가벼운|유쾌|웃긴|재밌는|부담\s*없이|편하게|머리\s*비우고|힐링")
_RESTFUL_QUERY = re.compile(
    r"잠들기\s*전|자기\s*전|잠자기\s*전|편안(?:하게|한)|잔잔(?:하게|한)|"
    r"조용(?:하게|한)|마음\s*편(?:하게|한)|차분(?:하게|한)"
)
_TOUCHING_QUERY = re.compile(r"감동|뭉클|눈물\s*나는|마음\s*따뜻")
_UPLIFT_QUERY = re.compile(r"우울할\s*때|기분\s*전환|기분이?\s*(?:안\s*좋|별로)|기운\s*없")
_FEELGOOD_QUERY = re.compile(
    r"보고\s*나면\s*기분(?:이)?\s*(?:좋|나아)|기분\s*좋아지는|"
    r"기분이?\s*(?:좀\s*)?나아|기분이\s*좋아질|행복해지|기분\s*좋게|"
    r"기운을?\s*북돋|우울한?\s*기분을?\s*털어|마음이?\s*환해|"
    r"긍정적인?\s*에너지|희망적인|다시\s*용기|용기\s*나는|"
    r"자신감(?:을|이)?\s*(?:되찾|생기|높)|힘이?\s*나는"
)
_DISCUSSION_QUERY = re.compile(
    r"(?:같이\s*)?얘기할\s*거리|생각할\s*거리|토론할\s*거리|"
    r"토론하기\s*좋|대화\s*나누기\s*좋|곱씹|여운이?\s*(?:남|긴)|"
    r"철학적|해석할\s*거리|여러\s*해석|결말.*의견이?\s*갈|"
    r"인간과?\s*사회.*질문"
)
_AVOID_SAD_QUERY = re.compile(
    r"(?:너무\s*)?(?:슬픈|슬프|슬퍼).*?(?:싫|말고|빼|제외)|"
    r"(?:싫|말고|빼|제외).*?(?:슬픈|슬프|슬퍼)|슬프지\s*않|"
    r"울적하게.*말고|눈물.*말고|비극적인?.*(?:제외|말고|빼)|"
    r"이별.*없는|마음\s*아픈.*싫|새드\s*엔딩\s*아닌|"
    r"(?:무겁고\s*)?우울한.*(?:빼|말고|제외)"
)
_ADULT_ANIMATION_QUERY = re.compile(
    r"(?:어른|성인)(?:이|도|들이?)?\s*(?:봐|보).*?(?:유치하지\s*않|유치하지\s*않은|애니)|"
    r"유치한?\s*(?:건|것은|애니는?)?\s*(?:싫|말고|빼|제외)|"
    r"성인이?\s*보기\s*좋은\s*애니|아이들용\s*말고\s*어른.*애니|"
    r"(?:주제가?\s*)?성숙한\s*애니|성인용\s*애니|"
    r"아동\s*애니\s*말고\s*깊이|어른\s*취향.*애니|"
    r"사회적인?\s*주제.*애니|유치하지\s*않고.*애니|성인\s*관객.*애니"
)
_DATE_QUERY = re.compile(r"데이트|연인(?:과|이랑)?|커플(?:이|끼리)?")
_FAMILY_COMFORT_QUERY = re.compile(
    r"(?:부모님|가족).{0,30}(?:민망|잔인하지|폭력적이지|편하게\s*같이)|"
    r"(?:민망|잔인하지|폭력적이지).{0,30}(?:부모님|가족)"
)
_GENTLE_SUSPENSE_QUERY = re.compile(
    r"(?:긴장감(?:은|이)?\s*(?:조금|살짝)|살짝\s*(?:쫄깃|긴장)|가볍게\s*쫄깃)|"
    r"(?:쫄깃|긴장감).{0,24}(?:안\s*무서|무섭지)|"
    r"(?:안\s*무서|무섭지).{0,24}(?:쫄깃|긴장감)"
)
_BRIGHT_ROMANCE_QUERY = re.compile(
    r"(?:밝|유쾌|설레).*?(?:데이트|로맨스|멜로)|"
    r"(?:데이트|로맨스|멜로).*?(?:밝|유쾌|설레)"
)
_KIDS_QUERY = re.compile(
    r"아이와|아이랑|아이하고|어린이와|어린이랑|자녀와|온\s*가족|"
    r"유치원생|미취학|초등생|초등학생|아동|(?:어린|어린이|초등생|초등학생)\s*조카|조카(?:랑|와|하고)"
)
_RECOMMENDATION_QUERY = re.compile(
    r"추천|볼\s*영화|보기\s*좋|보고\s*싶|뭐\s*볼|골라|"
    r"영화(?:가|를|을)?\s*(?:좋아|좋아해)"
)
_GROUP_COMPROMISE_QUERY = re.compile(
    r"(?:한\s*명은|나는|친구).{0,100}(?:다\s*같이|모두|넷\s*다|덜\s*불만|취향.{0,12}(?:맞|절충))"
)
_LIGHT_GENRES = {"코미디", "가족", "애니메이션", "로맨스", "모험", "음악"}
_RESTFUL_GENRES = {"드라마", "로맨스", "가족", "애니메이션", "음악", "코미디"}
_TOUCHING_GENRES = {"드라마", "가족", "애니메이션", "로맨스"}
_DATE_GENRES = {"로맨스", "코미디"}
_GENTLE_SUSPENSE_GENRES = {"미스터리", "코미디", "모험", "범죄", "스릴러"}
_KIDS_GENRES = {"가족", "애니메이션", "모험", "판타지", "코미디"}
_HEAVY_GENRES = {"공포", "스릴러", "범죄", "전쟁", "역사", "다큐멘터리"}
_INTENSE_GENRES = {"액션", "공포", "스릴러", "범죄", "전쟁"}
_DISCUSSION_GENRES = {"드라마", "미스터리", "SF", "다큐멘터리"}
_DISCUSSION_TERMS = re.compile(
    r"인간|사회|윤리|도덕|선택|정체성|소통|언어|기억|시간|의미|갈등|"
    r"미래|존재|편견|책임|질문|딜레마"
)
_FEELGOOD_TERMS = re.compile(r"유쾌|즐거|행복|희망|꿈|우정|사랑|성장|재회|도전|용기")
_FEELGOOD_NEGATIVE_TERMS = re.compile(r"살인|복수|전쟁|고문|죽음|공포|비극|학대|절망")
_BRIGHT_TERMS = re.compile(r"밝|유쾌|웃|행복|희망|설렘|새\s*출발|다시\s*시작|사랑")
_RESTFUL_TERMS = re.compile(r"편안|잔잔|조용|차분|평온|휴식|일상|위로|따뜻|힐링")
_INTENSE_TERMS = re.compile(r"전투|전쟁|폭발|추격|살인|복수|공포|위협|생존|재난")
_SAD_TERMS = re.compile(
    r"죽음|사별|이별|비극|상실|장례|시한부|말기암|"
    r"암|희귀병|불치병|병마|투병|시간이?\s*얼마\s*남지|우울|절망|눈물"
    r"|불안하고\s*상처\s*입|정신\s*착란|출구\s*없는|괴롭힘|두려움|괴로워|살인\s*사건|극단적"
)
_MATURE_ANIMATION_TERMS = re.compile(
    r"사회|정체성|관계|가족|갈등|편견|차별|책임|인간|삶|죽음|상실|전쟁|"
    r"홈리스|가출|범죄|정치|철학"
)
_CHILD_ORIENTED_TERMS = re.compile(r"유아|어린이용|아동용|꼬마|유치원")


def _with_explicit_genres(expanded: str, original: str) -> str:
    mentioned = [genre for genre in sorted(
        _LIGHT_GENRES | _RESTFUL_GENRES | _TOUCHING_GENRES | _DATE_GENRES | _KIDS_GENRES | _HEAVY_GENRES | {"액션", "SF", "판타지", "드라마", "미스터리", "뮤지컬"},
        key=len,
        reverse=True,
    ) if genre in original]
    return " ".join([expanded, *mentioned]) if mentioned else expanded


def expand_mood_query(query: str) -> str:
    """Replace ambiguous mood words with retrieval concepts represented in movie metadata."""
    if _ADULT_ANIMATION_QUERY.search(query):
        return _with_explicit_genres(
            "어른도 깊이 있게 볼 수 있는 성숙한 주제의 애니메이션 드라마 사회 관계 정체성 영화",
            query,
        )
    if _KIDS_QUERY.search(query):
        return _with_explicit_genres("어린이와 함께 보기 좋은 가족 애니메이션 모험 판타지 코미디 영화", query)
    if _FEELGOOD_QUERY.search(query):
        return _with_explicit_genres(
            "보고 나면 기분이 좋아지는 밝고 유쾌한 음악 코미디 우정 사랑 성장 희망 영화",
            query,
        )
    if _DISCUSSION_QUERY.search(query):
        return _with_explicit_genres(
            "보고 나서 함께 토론하고 생각할 거리가 많은 철학적 SF 드라마 미스터리 영화",
            query,
        )
    if _UPLIFT_QUERY.search(query):
        return _with_explicit_genres(
            "많은 관객에게 사랑받은 기분 전환이 되는 밝고 유쾌한 코미디 음악 우정 성장 영화",
            query,
        )
    if _RESTFUL_QUERY.search(query):
        return _with_explicit_genres(
            "잠들기 전 편안하고 잔잔하게 볼 수 있는 평온한 일상 위로 드라마 로맨스 가족 애니메이션 음악 영화",
            query,
        )
    if _FAMILY_COMFORT_QUERY.search(query):
        return _with_explicit_genres(
            "부모님과 함께 편하게 보고 이야기 나누기 좋은 가족 코미디 드라마 영화",
            query,
        )
    if _GENTLE_SUSPENSE_QUERY.search(query):
        return _with_explicit_genres(
            "무섭지 않으면서 가볍게 긴장감 있는 미스터리 코미디 케이퍼 모험 영화",
            query,
        )
    if _DATE_QUERY.search(query):
        if _AVOID_SAD_QUERY.search(query) or _BRIGHT_ROMANCE_QUERY.search(query):
            return _with_explicit_genres(
                "연인과 함께 보기 좋은 밝고 유쾌하며 설레는 로맨스 코미디 영화",
                query,
            )
        return _with_explicit_genres("연인과 함께 보기 좋은 로맨스 코미디 영화", query)
    if _TOUCHING_QUERY.search(query):
        return _with_explicit_genres("감동적이고 따뜻한 휴먼 드라마 가족 성장 우정 영화", query)
    if _LIGHT_QUERY.search(query):
        return _with_explicit_genres("밝고 유쾌하며 편안한 코미디 가족 애니메이션 로맨스 모험 영화", query)
    return query


def _genre_set(movie: dict) -> set[str]:
    raw = movie.get("genres_list") or movie.get("genres") or []
    if isinstance(raw, str):
        if raw.lstrip().startswith("["):
            try:
                parsed = json.loads(raw)
                return {str(genre).strip() for genre in parsed if str(genre).strip()}
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        return {genre.strip() for genre in raw.split(",") if genre.strip()}
    return {str(genre).strip() for genre in raw if str(genre).strip()}


def is_child_safe_certification(movie: dict) -> bool:
    country = str(movie.get("certification_country") or "").strip().upper()
    certification = re.sub(r"\s+", "", str(movie.get("certification") or "")).upper()
    if country == "US":
        return certification in {"G", "PG"}
    if country == "KR":
        return certification in {"ALL", "전체관람가"}
    return False


def _mood_policy(query: str) -> tuple[set[str], set[str]] | None:
    if _KIDS_QUERY.search(query):
        return _KIDS_GENRES, _HEAVY_GENRES
    if _RESTFUL_QUERY.search(query):
        return _RESTFUL_GENRES, _INTENSE_GENRES
    if _FAMILY_COMFORT_QUERY.search(query):
        return {"가족", "코미디", "드라마", "음악"}, {"공포", "전쟁", "범죄", "스릴러"}
    if _GENTLE_SUSPENSE_QUERY.search(query):
        return _GENTLE_SUSPENSE_GENRES, {"공포", "전쟁"}
    if _UPLIFT_QUERY.search(query) or _LIGHT_QUERY.search(query):
        return _LIGHT_GENRES, _HEAVY_GENRES
    if _AVOID_SAD_QUERY.search(query) or _BRIGHT_ROMANCE_QUERY.search(query):
        return _LIGHT_GENRES, _HEAVY_GENRES
    if _DATE_QUERY.search(query):
        return _DATE_GENRES, _HEAVY_GENRES
    if _TOUCHING_QUERY.search(query):
        return _TOUCHING_GENRES, {"공포"}
    return None


def apply_query_preferences(query: str, candidates: list[dict], required: int) -> list[dict]:
    """Apply only explicit mood preferences, with staged fallback to preserve recall."""
    policy = _mood_policy(query)
    if not policy:
        return candidates

    preferred_genres, blocked_genres = policy

    preferred = [
        movie for movie in candidates
        if _genre_set(movie) & preferred_genres and not (_genre_set(movie) & blocked_genres)
    ]

    if _KIDS_QUERY.search(query):
        rated_safe = [movie for movie in preferred if is_child_safe_certification(movie)]
        # Child safety is a hard constraint. Fewer cards are safer than silently
        # filling the result with unrated or adult-oriented movies.
        return rated_safe

    if len(preferred) >= required:
        return preferred

    non_heavy = [movie for movie in candidates if not (_genre_set(movie) & blocked_genres)]
    # Explicitly blocked genres remain blocked even when recall is low.
    return non_heavy


def prefer_well_received_candidates(query: str, candidates: list[dict], required: int) -> list[dict]:
    """Avoid poorly rated movies in recommendation requests when alternatives exist."""
    purpose_query = any(pattern.search(query) for pattern in (
        _LIGHT_QUERY, _RESTFUL_QUERY, _TOUCHING_QUERY, _UPLIFT_QUERY, _FEELGOOD_QUERY,
        _DISCUSSION_QUERY, _AVOID_SAD_QUERY, _ADULT_ANIMATION_QUERY,
        _BRIGHT_ROMANCE_QUERY, _GENTLE_SUSPENSE_QUERY, _FAMILY_COMFORT_QUERY, _DATE_QUERY, _KIDS_QUERY,
    ))
    if not _RECOMMENDATION_QUERY.search(query) and not purpose_query:
        return candidates
    acceptable = [movie for movie in candidates if float(movie.get("vote_average") or 0.0) >= 6.0]
    return acceptable if len(acceptable) >= required else candidates


def has_recommendation_evidence(movie: dict) -> bool:
    """Whether a movie has enough real-user evidence for a generic recommendation."""
    vote_count = max(int(movie.get("vote_count") or 0), 0)
    audience_count = max(int(movie.get("audience_count") or 0), 0)
    return vote_count >= MIN_RECOMMENDATION_VOTES or audience_count > 0


def prefer_evidenced_candidates(candidates: list[dict], required: int) -> list[dict]:
    """Use evidenced movies when there are enough, otherwise preserve recall."""
    evidenced = [movie for movie in candidates if has_recommendation_evidence(movie)]
    return evidenced if len(evidenced) >= required else candidates


def prefer_explainable_candidates(query: str, candidates: list[dict], required: int) -> list[dict]:
    """Prefer candidates with synopsis evidence for explicit viewing-purpose requests."""
    purpose_query = any(pattern.search(query) for pattern in (
        _LIGHT_QUERY, _RESTFUL_QUERY, _TOUCHING_QUERY, _UPLIFT_QUERY, _FEELGOOD_QUERY,
        _DISCUSSION_QUERY, _AVOID_SAD_QUERY, _ADULT_ANIMATION_QUERY,
        _BRIGHT_ROMANCE_QUERY, _GENTLE_SUSPENSE_QUERY, _FAMILY_COMFORT_QUERY, _DATE_QUERY, _KIDS_QUERY,
    ))
    if not purpose_query:
        return candidates
    explainable = [movie for movie in candidates if str(movie.get("overview") or "").strip()]
    return explainable if len(explainable) >= required else candidates


def prefer_non_sad_candidates(query: str, candidates: list[dict], required: int) -> list[dict]:
    """Remove synopsis-backed tragic candidates when the user explicitly rejects sadness."""
    if not (_AVOID_SAD_QUERY.search(query) or _BRIGHT_ROMANCE_QUERY.search(query)):
        return candidates
    non_sad = [
        movie for movie in candidates
        if not _SAD_TERMS.search(str(movie.get("overview") or ""))
    ]
    return non_sad if len(non_sad) >= required else candidates


def prefer_bright_candidates(query: str, candidates: list[dict], required: int) -> list[dict]:
    """Require synopsis-backed positive evidence for explicitly bright romance."""
    if not _BRIGHT_ROMANCE_QUERY.search(query):
        return candidates
    bright = [
        movie for movie in candidates
        if _BRIGHT_TERMS.search(str(movie.get("overview") or ""))
    ]
    return bright if len(bright) >= required else candidates


def movie_quality_score(movie: dict) -> float:
    """Return a 0..1 confidence score without treating a few perfect votes as reliable."""
    vote_count = max(int(movie.get("vote_count") or 0), 0)
    audience_count = max(int(movie.get("audience_count") or 0), 0)
    vote_average = min(max(float(movie.get("vote_average") or 0.0), 0.0), 10.0)

    popularity = min(math.log1p(vote_count) / math.log1p(5000), 1.0)
    audience = min(math.log1p(audience_count) / math.log1p(1_000_000), 1.0)
    rating_confidence = min(math.log1p(vote_count) / math.log1p(100), 1.0)
    trusted_rating = (vote_average / 10.0) * rating_confidence

    metadata_parts = (
        bool(str(movie.get("overview") or "").strip()),
        bool(str(movie.get("poster_path") or "").strip()),
        bool(str(movie.get("genres") or "").strip()),
        bool(str(movie.get("release_date") or movie.get("year") or "").strip()),
    )
    metadata = sum(metadata_parts) / len(metadata_parts)

    return min(1.0, 0.50 * popularity + 0.25 * trusted_rating + 0.10 * audience + 0.15 * metadata)


def intent_match_score(query: str, movie: dict) -> float | None:
    """Score explicit viewing-purpose evidence in existing movie metadata."""
    genres = _genre_set(movie)
    text = " ".join(
        str(movie.get(field) or "") for field in ("overview", "text", "keywords")
    )

    if _GROUP_COMPROMISE_QUERY.search(query):
        requested = {genre for genre in _with_explicit_genres("", query).split() if genre in {
            "액션", "코미디", "미스터리", "로맨스", "SF", "판타지", "모험", "드라마", "가족", "음악"
        }}
        coverage = len(genres & requested) / max(len(requested), 1)
        country = str(movie.get("certification_country") or "").strip().upper()
        certification = re.sub(r"\s+", "", str(movie.get("certification") or "")).upper()
        adult_penalty = 0.35 if certification in {"R", "NC-17", "18", "청소년관람불가"} else 0.0
        return min(1.0, max(0.0, coverage - adult_penalty))

    if _GENTLE_SUSPENSE_QUERY.search(query):
        genre_bonus = 0.22 * len(genres & _GENTLE_SUSPENSE_GENRES)
        intense_penalty = 0.28 * len(genres & {"공포", "전쟁"})
        return min(1.0, max(0.0, genre_bonus - intense_penalty))

    if _FAMILY_COMFORT_QUERY.search(query):
        positive = 0.20 * len(genres & {"가족", "코미디", "드라마", "음악"})
        intense = 0.28 * len(genres & {"공포", "전쟁", "범죄", "스릴러"})
        intense += 0.14 * len(set(_INTENSE_TERMS.findall(text)))
        return min(1.0, max(0.0, positive - intense))

    if _RESTFUL_QUERY.search(query):
        restful_genres = len(genres & _RESTFUL_GENRES)
        restful_terms = len(set(_RESTFUL_TERMS.findall(text)))
        intense_genres = len(genres & _INTENSE_GENRES)
        intense_terms = len(set(_INTENSE_TERMS.findall(text)))
        return min(
            1.0,
            max(
                0.0,
                0.16 * restful_genres
                + 0.14 * restful_terms
                - 0.24 * intense_genres
                - 0.18 * intense_terms,
            ),
        )

    if _DISCUSSION_QUERY.search(query):
        term_count = len(set(_DISCUSSION_TERMS.findall(text)))
        genre_bonus = 0.25 if genres & _DISCUSSION_GENRES else 0.0
        return min(1.0, genre_bonus + 0.18 * term_count)

    if _ADULT_ANIMATION_QUERY.search(query):
        mature_terms = len(set(_MATURE_ANIMATION_TERMS.findall(text)))
        child_terms = len(set(_CHILD_ORIENTED_TERMS.findall(text)))
        mature_genre_bonus = 0.20 if genres & {"드라마", "미스터리", "범죄", "역사", "전쟁"} else 0.0
        country = str(movie.get("certification_country") or "").strip().upper()
        certification = re.sub(r"\s+", "", str(movie.get("certification") or "")).upper()
        rating_bonus = 0.15 if (
            (country == "KR" and certification in {"12", "15", "18", "청소년관람불가"})
            or (country == "US" and certification in {"PG-13", "R", "NC-17"})
        ) else 0.0
        return min(1.0, max(0.0, mature_genre_bonus + rating_bonus + 0.12 * mature_terms - 0.20 * child_terms))

    if _FEELGOOD_QUERY.search(query):
        positive_genres = len(genres & _LIGHT_GENRES)
        positive_terms = len(set(_FEELGOOD_TERMS.findall(text)))
        negative_terms = len(set(_FEELGOOD_NEGATIVE_TERMS.findall(text)))
        return min(1.0, max(0.0, 0.18 * positive_genres + 0.14 * positive_terms - 0.20 * negative_terms))

    if _AVOID_SAD_QUERY.search(query) or _BRIGHT_ROMANCE_QUERY.search(query):
        positive_terms = len(set(_BRIGHT_TERMS.findall(text)))
        negative_terms = len(set(_SAD_TERMS.findall(text)))
        comedy_bonus = 0.25 if "코미디" in genres else 0.0
        return min(1.0, max(0.0, comedy_bonus + 0.15 * positive_terms - 0.22 * negative_terms))

    return None


def blend_semantic_and_quality(
    ranked: list[dict],
    top_k: int,
    quality_weight: float = 0.30,
    query: str = "",
) -> list[dict]:
    """Blend CrossEncoder relevance with evidence quality while preserving strong matches."""
    if not ranked:
        return []

    scores = [float(movie.get("_score") or 0.0) for movie in ranked]
    low, high = min(scores), max(scores)
    span = high - low
    semantic_weight = 1.0 - quality_weight

    rescored = []
    for index, movie in enumerate(ranked):
        if span > 1e-9:
            semantic = (float(movie.get("_score") or 0.0) - low) / span
        else:
            semantic = 1.0 - (index / max(len(ranked) - 1, 1))
        quality = movie_quality_score(movie)
        intent = intent_match_score(query, movie)
        if intent is None:
            final_score = semantic_weight * semantic + quality_weight * quality
        else:
            final_score = 0.45 * semantic + 0.25 * quality + 0.30 * intent
        rescored.append(dict(movie, _final_score=final_score))

    rescored.sort(key=lambda movie: movie["_final_score"], reverse=True)
    return rescored[:top_k]

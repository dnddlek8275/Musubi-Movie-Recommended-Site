"""영화 키워드로 장르별 중심도를 추정하는 경량 관련도 계산기."""

from __future__ import annotations

import re

from sqlalchemy import delete, select


GENRE_WEIGHT_VERSION = "genre-keywords-overview-v4"
GENRE_RELEVANCE_MINIMUM = 0.6


# TMDB 장르 배열의 순서는 중요도를 보장하지 않으므로 사용하지 않는다.
# 각 장르를 직접 뒷받침하는 한국어·영어 키워드만 보조 근거로 사용한다.
GENRE_KEYWORD_SIGNALS: dict[str, tuple[str, ...]] = {
    "드라마": ("drama", "relationship", "family conflict", "coming of age", "사회", "갈등", "성장"),
    "코미디": ("comedy", "humor", "parody", "satire", "slapstick", "코미디", "유머", "풍자"),
    "스릴러": ("thriller", "suspense", "conspiracy", "chase", "survival", "스릴러", "긴장", "추격"),
    "액션": ("action", "martial arts", "fight", "gunfight", "combat", "superhero", "액션", "격투", "총격"),
    "공포": ("horror", "ghost", "demon", "haunted", "monster", "zombie", "공포", "유령", "악령"),
    "로맨스": (
        "romance", "romantic", "love", "falling in love", "love story",
        "love triangle", "first love", "dating", "wedding", "marriage",
        "ex-girlfriend", "ex-boyfriend", "reunion", "로맨스", "연애",
        "사랑", "연인", "첫사랑", "결혼", "이별", "재회",
    ),
    "범죄": ("crime", "murder", "police", "detective", "gangster", "heist", "범죄", "살인", "경찰", "형사"),
    "모험": ("adventure", "journey", "expedition", "treasure", "quest", "모험", "여행", "탐험", "보물"),
    "애니메이션": ("animation", "anime", "cartoon", "stop motion", "애니메이션", "애니", "만화"),
    "sf": ("science fiction", "sci-fi", "space", "alien", "robot", "future", "time travel", "우주", "외계인", "로봇", "미래"),
    "가족": ("family", "children", "parent", "child", "family friendly", "가족", "어린이", "부모"),
    "tv 영화": ("television movie", "tv movie", "made for television", "television special", "tv 스페셜"),
    "판타지": ("fantasy", "magic", "wizard", "mythical", "fairy tale", "dragon", "판타지", "마법", "마법사"),
    "미스터리": ("mystery", "investigation", "secret", "unsolved", "whodunit", "미스터리", "수수께끼", "비밀"),
    "다큐멘터리": ("documentary", "interview", "archive footage", "biography", "다큐멘터리", "인터뷰", "기록"),
    "음악": ("music", "musical", "singer", "band", "concert", "dance", "음악", "가수", "밴드", "콘서트"),
    "서부": ("western", "cowboy", "sheriff", "outlaw", "frontier", "서부", "카우보이", "보안관"),
    "역사": ("history", "historical", "period drama", "biography", "ancient", "역사", "시대극", "실화"),
    "전쟁": ("war", "soldier", "military", "battle", "army", "warfare", "전쟁", "군인", "전투", "군대"),
}


def _normalize(value: object) -> str:
    return str(value or "").strip().casefold()


def _contains_signal(keyword: str, signal: str) -> bool:
    if re.search(r"[가-힣]", signal):
        return signal in keyword
    return bool(re.search(rf"(?<!\w){re.escape(signal)}(?!\w)", keyword))


def _signal_occurrences(text: str, signal: str) -> int:
    if re.search(r"[가-힣]", signal):
        return text.count(signal)
    return len(re.findall(rf"(?<!\w){re.escape(signal)}(?!\w)", text))


def genre_relevance_details(movie) -> dict[str, dict[str, float | int]]:
    """영화별 장르 중심도와 이를 뒷받침한 키워드 수를 반환한다."""
    genres = list(dict.fromkeys(
        _normalize(value) for value in (movie.genres or []) if _normalize(value)
    ))
    if not genres:
        return {}
    keywords = {
        _normalize(value) for value in (movie.keywords or []) if _normalize(value)
    }
    overview = _normalize(getattr(movie, "overview", None))
    hits: dict[str, int] = {}
    for genre in genres:
        signals = GENRE_KEYWORD_SIGNALS.get(genre, ())
        hits[genre] = sum(
            2 if any(_contains_signal(keyword, signal) for keyword in keywords) else 0
            for signal in signals
        ) + sum(
            min(_signal_occurrences(overview, signal), 2)
            for signal in signals
        )
    maximum = max(hits.values(), default=0)
    if maximum == 0:
        return {
            genre: {"weight": 0.6, "evidence_count": 0}
            for genre in genres
        }
    return {
        genre: {
            "weight": round(0.15 if count == 0 else 0.35 + 0.65 * count / maximum, 4),
            "evidence_count": count,
        }
        for genre, count in hits.items()
    }


def genre_relevance_scores(movie) -> dict[str, float]:
    return {
        genre: float(detail["weight"])
        for genre, detail in genre_relevance_details(movie).items()
    }


def genre_relevance_score(movie, genre: str) -> float:
    return genre_relevance_scores(movie).get(_normalize(genre), 0.0)


def weighted_genre_similarity(source, candidate) -> float | None:
    """두 영화의 장르 중심도를 반영한 weighted Jaccard 유사도."""
    left = genre_relevance_scores(source)
    right = genre_relevance_scores(candidate)
    if not left or not right:
        return None
    genres = set(left) | set(right)
    denominator = sum(max(left.get(genre, 0.0), right.get(genre, 0.0)) for genre in genres)
    if denominator == 0:
        return None
    numerator = sum(min(left.get(genre, 0.0), right.get(genre, 0.0)) for genre in genres)
    return numerator / denominator


def sync_movie_genre_weights(db, movie) -> int:
    """현재 장르·키워드에서 계산한 가중치 행을 같은 트랜잭션에 동기화한다."""
    from app.models.movies import MovieGenreWeight

    db.execute(delete(MovieGenreWeight).where(MovieGenreWeight.movie_id == movie.id))
    details = genre_relevance_details(movie)
    for genre, detail in details.items():
        db.add(MovieGenreWeight(
            movie_id=movie.id,
            genre=genre,
            weight=float(detail["weight"]),
            evidence_count=int(detail["evidence_count"]),
            calculation_version=GENRE_WEIGHT_VERSION,
        ))
    return len(details)


def load_genre_weight_map(db, movie_ids: list[int]) -> dict[tuple[int, str], float]:
    """여러 영화의 저장된 장르 가중치를 추천·검색용 매핑으로 한 번에 읽는다."""
    from app.models.movies import MovieGenreWeight

    if not movie_ids:
        return {}
    rows = db.execute(
        select(
            MovieGenreWeight.movie_id,
            MovieGenreWeight.genre,
            MovieGenreWeight.weight,
        ).where(MovieGenreWeight.movie_id.in_(movie_ids))
    ).all()
    return {
        (movie_id, _normalize(genre)): float(weight)
        for movie_id, genre, weight in rows
    }


from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.interactions import MovieRating, MovieWishlist, UserMovieInteraction
from app.models.movies import Movie
from app.models.users import User, UserPreferenceScore
from app.services.movies.genre_relevance import (
    GENRE_RELEVANCE_MINIMUM,
    genre_relevance_score,
)


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


PREFERENCE_ACTION_SCORE = {
    "view": 0.1,
    "search_click": 1.5,
    "like": 3.0,
}
PREFERENCE_HALF_LIFE_DAYS = 30.0
EXPLICIT_PREFERENCE_SCORE = 3.0
WISHLIST_PREFERENCE_SCORE = 2.0
RATING_PREFERENCE_MAX_SCORE = 2.5

# 행동 한 번이 조연 배우들의 전체 필모그래피까지 취향으로 넓어지지 않도록
# 상위 출연진 3명만 학습하고 배우 몫은 전체 점수의 8%로 제한한다.
CORE_PREFERENCE_LIMITS = {"genre": 5, "actor": 3, "keyword": 8}
CORE_PREFERENCE_SHARES = {"genre": 0.57, "actor": 0.08, "keyword": 0.35}

# 2026-08-11 키워드 체계 정리 전 목록. 롤백 및 기존 점수 해석을 위해 보존한다.
LEGACY_LEARNABLE_KEYWORDS = {
    "based on novel or book", "based on true story", "based on webcomic or webtoon",
    "revenge", "friendship", "love", "romance", "romcom", "bromance",
    "coming of age", "family", "family secrets", "sibling relationship",
    "detective", "superhero", "superhero team", "secret identity", "villain",
    "dystopia", "post-apocalyptic future", "supernatural", "magic", "witch",
    "time travel", "teleportation", "survival", "fight for survival", "escape",
    "road trip", "sports", "martial arts", "alien", "aliens", "alien invasion",
    "dark comedy", "satire", "parody", "musical", "animation", "fairy tale",
    "zombie", "zombie apocalypse", "gore", "cybercrime", "hacker",
    "artificial intelligence (a.i.)", "virtual reality", "mind control", "mutation",
    "political conspiracy", "undercover operation", "historical event", "world war ii",
    "pacifism", "corruption", "ambition", "freedom", "hope", "melancholy",
    "loss of loved one", "dysfunctional family", "teenage romance", "high school",
    "mermaid", "boarding school", "maze", "jazz", "dance", "dancing", "prison",
    "소설·책 원작", "실화 바탕", "웹툰 원작", "복수", "우정", "사랑", "로맨스",
    "브로맨스", "성장", "가족", "가족의 비밀", "형제자매 관계", "탐정·추리",
    "슈퍼히어로", "숨겨진 정체", "악당", "디스토피아", "포스트 아포칼립스",
    "초자연", "마법", "마녀", "시간 여행", "생존", "로드 트립", "스포츠", "무술",
    "외계 생명체", "외계 침공", "블랙 코미디", "풍자", "패러디", "뮤지컬",
    "애니메이션", "동화", "좀비", "고어", "사이버 범죄", "해커", "인공지능",
    "가상현실", "정신 조종", "돌연변이", "정치적 음모", "잠입 작전", "역사적 사건",
    "제2차 세계대전", "평화주의", "부패", "야망", "자유", "희망", "상실", "십 대 로맨스",
}

# 현재 활성 체계는 영어·한국어 중복과 유사 개념을 대표 영문 키 하나로 합친다.
# 온보딩도 이 순서를 그대로 사용하므로, 학습용 키워드와 화면 선택지가 어긋나지 않는다.
# 기존 70개 의미 단위를 60개로 정리하되, 미로와 순간이동처럼 지나치게 세부적인
# 설정만 제외한다. USE_CURATED_KEYWORD_TAXONOMY=False로 바꾸면 이전 허용 방식으로
# 즉시 되돌릴 수 있다.
USE_CURATED_KEYWORD_TAXONOMY = True
CURATED_LEARNABLE_KEYWORD_ORDER = (
    "based on novel or book", "based on true story", "based on webcomic or webtoon",
    "animation", "musical", "fairy tale", "romance", "romcom", "friendship",
    "bromance", "family", "family secrets", "sibling relationship", "coming of age",
    "high school", "boarding school", "revenge", "detective", "superhero",
    "secret identity", "villain", "dystopia", "post-apocalyptic future",
    "supernatural", "magic", "witch", "mermaid", "time travel", "survival",
    "escape", "road trip", "sports", "martial arts", "alien", "alien invasion",
    "zombie", "gore", "dark comedy", "satire", "parody", "cybercrime", "hacker",
    "artificial intelligence (a.i.)", "virtual reality", "mind control", "mutation",
    "political conspiracy", "undercover operation", "historical event", "world war ii",
    "pacifism", "corruption", "ambition", "freedom", "hope", "loss of loved one",
    "melancholy", "prison", "dance", "jazz",
)
CURATED_LEARNABLE_KEYWORDS = set(CURATED_LEARNABLE_KEYWORD_ORDER)

KEYWORD_CANONICAL_MAP = {
    # 영문 유사 표현
    "aliens": "alien",
    "love": "romance",
    "teenage romance": "romance",
    "dysfunctional family": "family secrets",
    "fight for survival": "survival",
    "superhero team": "superhero",
    "zombie apocalypse": "zombie",
    "dancing": "dance",
    # 한국어 별칭
    "소설·책 원작": "based on novel or book",
    "실화 바탕": "based on true story",
    "웹툰 원작": "based on webcomic or webtoon",
    "복수": "revenge",
    "우정": "friendship",
    "사랑": "romance",
    "로맨스": "romance",
    "브로맨스": "bromance",
    "성장": "coming of age",
    "가족": "family",
    "가족의 비밀": "family secrets",
    "형제자매 관계": "sibling relationship",
    "탐정·추리": "detective",
    "슈퍼히어로": "superhero",
    "숨겨진 정체": "secret identity",
    "악당": "villain",
    "디스토피아": "dystopia",
    "포스트 아포칼립스": "post-apocalyptic future",
    "초자연": "supernatural",
    "마법": "magic",
    "마녀": "witch",
    "시간 여행": "time travel",
    "생존": "survival",
    "로드 트립": "road trip",
    "스포츠": "sports",
    "무술": "martial arts",
    "외계 생명체": "alien",
    "외계 침공": "alien invasion",
    "블랙 코미디": "dark comedy",
    "풍자": "satire",
    "패러디": "parody",
    "뮤지컬": "musical",
    "애니메이션": "animation",
    "동화": "fairy tale",
    "좀비": "zombie",
    "고어": "gore",
    "사이버 범죄": "cybercrime",
    "해커": "hacker",
    "인공지능": "artificial intelligence (a.i.)",
    "가상현실": "virtual reality",
    "정신 조종": "mind control",
    "돌연변이": "mutation",
    "정치적 음모": "political conspiracy",
    "잠입 작전": "undercover operation",
    "역사적 사건": "historical event",
    "제2차 세계대전": "world war ii",
    "평화주의": "pacifism",
    "부패": "corruption",
    "야망": "ambition",
    "자유": "freedom",
    "희망": "hope",
    "상실": "loss of loved one",
    "십 대 로맨스": "romance",
}


def canonicalize_keyword(value: str | None) -> str:
    normalized = (value or "").strip().casefold()
    if not normalized or not USE_CURATED_KEYWORD_TAXONOMY:
        return normalized
    return KEYWORD_CANONICAL_MAP.get(normalized, normalized)


def keyword_aliases_for(value: str | None) -> list[str]:
    """대표 키와 같은 의미인 DB 원문 키를 배열 검색용으로 반환한다."""
    canonical = canonicalize_keyword(value)
    if not canonical:
        return []
    if not USE_CURATED_KEYWORD_TAXONOMY:
        return [canonical]
    aliases = {
        item for item in LEGACY_LEARNABLE_KEYWORDS
        if canonicalize_keyword(item) == canonical
    }
    aliases.add(canonical)
    return sorted(aliases)

PREFERENCE_TYPES = {
    "genre",
    "actor",
    "director",
    "keyword",
    "language",
    "character",
}

def get_user_preference_scores(db, user_id):
    rows = list(
        db.scalars(
            select(UserPreferenceScore)
            .where(UserPreferenceScore.user_id == user_id)
            .order_by(UserPreferenceScore.score.desc())
        ).all()
    )
    return [
        row for row in rows
        if row.preference_type != "keyword" or is_learnable_keyword(row.preference_value)
    ]


def is_learnable_keyword(value: str | None) -> bool:
    if not value:
        return False
    if not USE_CURATED_KEYWORD_TAXONOMY:
        return value.strip().casefold() in LEGACY_LEARNABLE_KEYWORDS
    return canonicalize_keyword(value) in CURATED_LEARNABLE_KEYWORDS


@dataclass(frozen=True)
class PreferenceSignal:
    preference_type: str
    preference_value: str
    score: float
    behavior_score: float = 0.0
    explicit: bool = False


def _decayed_score(score: float, updated_at, now: datetime | None = None) -> float:
    if not updated_at:
        return float(score or 0.0)
    current = now or datetime.now(ZoneInfo("Asia/Seoul"))
    timestamp = updated_at
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
    age_days = max((current - timestamp).total_seconds() / 86_400, 0.0)
    return float(score or 0.0) * (0.5 ** (age_days / PREFERENCE_HALF_LIFE_DAYS))


def rating_preference_signal(score: float) -> float:
    """0.5~5점 평가를 완화된 -1.5~+2.5 취향 신호로 변환한다."""
    centered = (float(score) - 3.0) / 2.0
    return centered * RATING_PREFERENCE_MAX_SCORE * (0.6 if centered < 0 else 1.0)


def get_combined_user_preference_signals(db: Session, user_id: int) -> list[PreferenceSignal]:
    """직접 선택한 취향과 시간 감쇠된 행동 취향을 추천 계산 시점에만 결합한다."""
    user = get_user(db, user_id)
    if user is None:
        return []
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    totals: dict[tuple[str, str], float] = defaultdict(float)
    behavior_totals: dict[tuple[str, str], float] = defaultdict(float)
    explicit_keys: set[tuple[str, str]] = set()
    labels: dict[tuple[str, str], str] = {}
    for row in get_user_preference_scores(db, user_id):
        value = (row.preference_value or "").strip()
        if not value:
            continue
        if row.preference_type == "keyword":
            value = canonicalize_keyword(value)
        key = (row.preference_type, value.casefold())
        effective_score = _decayed_score(row.score, row.updated_at, now)
        totals[key] += effective_score
        behavior_totals[key] += effective_score
        labels[key] = value

    # 별점과 찜은 행동 이벤트로 복제하지 않고 원본 테이블에서 직접 계산한다.
    # 낮은 별점은 약한 부정 신호, 높은 별점과 찜은 긍정 신호로 사용한다.
    reset_at = user.preference_learning_reset_at
    rating_query = (
        select(MovieRating, Movie)
        .join(Movie, Movie.id == MovieRating.movie_id)
        .where(MovieRating.user_id == user_id)
    )
    wishlist_query = (
        select(MovieWishlist, Movie)
        .join(Movie, Movie.id == MovieWishlist.movie_id)
        .where(MovieWishlist.user_id == user_id)
    )
    if reset_at is not None:
        rating_query = rating_query.where(MovieRating.updated_at >= reset_at)
        wishlist_query = wishlist_query.where(MovieWishlist.created_at >= reset_at)

    rated_movies = db.execute(rating_query).all()
    wishlisted_movies = db.execute(wishlist_query).all()

    def add_movie_signal(movie: Movie, signal: float, occurred_at) -> None:
        if signal == 0:
            return
        decayed_signal = _decayed_score(signal, occurred_at, now)
        for preference_type, weighted_values in core_movie_preference_items(movie).items():
            if not weighted_values:
                continue
            total_weight = sum(weight for _, weight in weighted_values)
            for value, value_weight in weighted_values:
                key = (preference_type, value.casefold())
                delta = (
                    decayed_signal
                    * CORE_PREFERENCE_SHARES[preference_type]
                    * value_weight
                    / total_weight
                )
                totals[key] += delta
                behavior_totals[key] += delta
                labels[key] = value

    for rating, movie in rated_movies:
        # 부정 신호는 한 편의 낮은 평가가 장르 전체를 지우지 않도록 완화한다.
        signal = rating_preference_signal(float(rating.score))
        add_movie_signal(movie, signal, rating.updated_at or rating.created_at)
    for wishlist, movie in wishlisted_movies:
        add_movie_signal(movie, WISHLIST_PREFERENCE_SCORE, wishlist.created_at)

    explicit = {
        "genre": user.preferred_genres or [],
        "actor": user.preferred_actors or [],
        "keyword": user.preferred_keywords or [],
        "director": user.preferred_directors or [],
    }
    for preference_type, values in explicit.items():
        for value in dict.fromkeys(item.strip() for item in values if item and item.strip()):
            if preference_type == "keyword":
                value = canonicalize_keyword(value)
                if not is_learnable_keyword(value):
                    continue
            key = (preference_type, value.casefold())
            totals[key] += EXPLICIT_PREFERENCE_SCORE
            explicit_keys.add(key)
            labels[key] = value

    return sorted(
        (
            PreferenceSignal(
                preference_type,
                labels[(preference_type, normalized)],
                score,
                behavior_totals[(preference_type, normalized)],
                (preference_type, normalized) in explicit_keys,
            )
            for (preference_type, normalized), score in totals.items()
            if abs(score) > 1e-9
        ),
        key=lambda item: item.score,
        reverse=True,
    )


def save_onboarding_preferences(
    db: Session,
    user: User,
    genres: list[str],
    actors: list[str],
    keywords: list[str],
    onboarding_completed: bool,
):
    """온보딩에서 직접 고른 취향을 저장하고 추천용 초기 점수를 만든다."""

    def normalize(values):
        return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))

    normalized = {
        "genre": normalize(genres),
        "actor": normalize(actors),
        "keyword": normalize(keywords),
    }

    user.preferred_genres = normalized["genre"]
    user.preferred_actors = normalized["actor"]
    user.preferred_keywords = normalized["keyword"]
    user.onboarding_completed = onboarding_completed

    # 명시적 취향 변경 시 과거 배열 값이 학습 점수에 남지 않도록 현재 행동
    # 기록과 새 명시적 선택을 기준으로 전체 점수를 일관되게 다시 계산한다.
    rebuild_user_preference_scores(db, user.id)

    db.commit()
    db.refresh(user)

    return {
        "genres": user.preferred_genres or [],
        "actors": user.preferred_actors or [],
        "keywords": user.preferred_keywords or [],
        "onboarding_completed": user.onboarding_completed,
    }

def delete_my_preference_result(
        db: Session,
        user_id : int,
        preference_type : str,
        preference_value : str,
):
    user = get_user(db, user_id)

    if not user:
        return {
            "state" : "failure",
            "message" : "DB에서 사용자 정보가 없음"
        }
    
    preference_column_map = {
        "genre" : User.preferred_genres,
        "actor" : User.preferred_actors,
        "keyword" : User.preferred_keywords,
    }

    if preference_type not in preference_column_map:
        return {
            "state" : "failure",
            "message" : "허용되지 않는 타입입니다."
        }
    
    target_column = preference_column_map[preference_type]

    # DB에서 배열 컬럼안의 선호 값 하나만 제거
    db.query(User).filter(User.id == user_id).update(
        {
            target_column : func.array_remove(target_column, preference_value)
        },
        synchronize_session=False
    )
    db.commit()
    return {
        "state" : "success",
        "message" : "사용자의 선호값 삭제 성공",
        "data" : {
            "preferred_genres" : user.preferred_genres,
            "preferred_actors" : user.preferred_actors,
            "preferred_keywords" : user.preferred_keywords,
        }
    }
    

# 사용자 해동 점수 누적
def add_user_preference_score(
        db : Session,
        user_id : int,
        preference_type : str,
        preference_value : str,
        action_type : str,
):
    # 액션 형태를 받지 않은 경우 False로 반환
    if not preference_value or not preference_type or not action_type:
        return False
    
    # 저장 형태 앞뒤 공백 제거
    preference_type = preference_type.strip()
    preference_value = preference_value.strip()
    action_type = action_type.strip()

    if not preference_type or not preference_value or not action_type:
        return False
    if preference_type not in PREFERENCE_TYPES:
        return False
    if preference_type == "keyword":
        if not is_learnable_keyword(preference_value):
            return False
        preference_value = canonicalize_keyword(preference_value)
    
    score_delta = PREFERENCE_ACTION_SCORE.get(action_type)

    # 지원하지 않는 행동은 점수를 반영하지 않는다.
    if score_delta is None:
        return False
    
    # 저장된 점수가 DB에 있는 경우 편집
    preference_score = db.scalar(
        select(UserPreferenceScore)
        .where(
            UserPreferenceScore.user_id == user_id,
            UserPreferenceScore.preference_type == preference_type,
            UserPreferenceScore.preference_value == preference_value,
        )
    )

    # 이미 있는 점수면 score 컬럼에 누적
    if preference_score:
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        preference_score.score = _decayed_score(
            preference_score.score, preference_score.updated_at, now
        ) + score_delta
        preference_score.updated_at = now

    else :
        # 처음 발생한 행동이면 새로운 행 생성
        preference_score = UserPreferenceScore(
            user_id = user_id,
            preference_type = preference_type,
            preference_value = preference_value,
            score = score_delta,
        )
        db.add(preference_score)
        
    return True


# 사용자가 영화 한편의 메타데이터를 사용자 취향 점수로 반영
def add_movie_preference_scores(
        db : Session,
        user_id : int,
        movie,
        action_type : str,
):

    action_score = PREFERENCE_ACTION_SCORE.get(action_type)
    if action_score is None:
        return 0

    added_count = 0
    for preference_type, weighted_values in core_movie_preference_items(movie).items():
        if not weighted_values:
            continue
        total_weight = sum(weight for _, weight in weighted_values)
        for preference_value, value_weight in weighted_values:
            per_value_score = (
                action_score
                * CORE_PREFERENCE_SHARES[preference_type]
                * value_weight
                / total_weight
            )
            preference_score = db.scalar(
                select(UserPreferenceScore).where(
                    UserPreferenceScore.user_id == user_id,
                    UserPreferenceScore.preference_type == preference_type,
                    UserPreferenceScore.preference_value == preference_value,
                )
            )
            if preference_score is None:
                db.add(UserPreferenceScore(
                    user_id=user_id,
                    preference_type=preference_type,
                    preference_value=preference_value,
                    score=per_value_score,
                ))
            else:
                now = datetime.now(ZoneInfo("Asia/Seoul"))
                preference_score.score = _decayed_score(
                    preference_score.score, preference_score.updated_at, now
                ) + per_value_score
                preference_score.updated_at = now
            added_count += 1
    return added_count


def core_movie_preference_values(movie) -> dict[str, list[str]]:
    """행동 학습에 사용하는 장르·배우·키워드를 영화별 상한 안에서 반환한다."""
    return {
        preference_type: [value for value, _ in weighted_values]
        for preference_type, weighted_values in core_movie_preference_items(movie).items()
    }


def core_movie_preference_items(movie) -> dict[str, list[tuple[str, float]]]:
    """영화 취향 신호와 영화 안에서의 상대적 중요도를 함께 반환한다."""
    raw_values = {
        "genre": movie.genres or [],
        "actor": movie.cast or [],
        "keyword": movie.keywords or [],
    }
    result = {}
    for preference_type, values in raw_values.items():
        normalized = list(dict.fromkeys(
            value.strip()
            for value in values
            if isinstance(value, str) and value.strip()
        ))
        if preference_type == "keyword":
            normalized = list(dict.fromkeys(
                canonicalize_keyword(value)
                for value in normalized
                if is_learnable_keyword(value)
            ))
        limited = normalized[:CORE_PREFERENCE_LIMITS[preference_type]]
        if preference_type == "genre":
            result[preference_type] = [
                (value, weight)
                for value in limited
                if (weight := genre_relevance_score(movie, value)) >= GENRE_RELEVANCE_MINIMUM
            ]
        else:
            result[preference_type] = [(value, 1.0) for value in limited]
    return result

# 사용자가 영화 한편의 메타데이터를 개인 취향 점수에 사용할 값을 꺼낸다.
def iter_movie_preference_values(movie):
    # 영화 필드를 취향 종류별 목록으로 변환
    movie_preferences = {
        "genre" : movie.genres or [],
        "actor" : movie.cast or [],
        "keyword" : movie.keywords or [],
        # 문자열 하나 - 리스트로 감싸기
        "director" : [movie.director] if movie.director else [],
        "language" : [movie.language] if movie.language else [],
    }

    # 같은 영화 안에 값이 중복되어도 한번반 반영
    for preference_type, values in movie_preferences.items():
        unique_values = {
            value.strip()
            for value in values
            if isinstance(value, str) and value.strip()
        }

        for preference_value in unique_values:
            yield preference_type, preference_value


def rebuild_user_preference_scores(db: Session, user_id: int) -> int:
    """명시적 취향과 일별 중복 제거 행동으로 한 사용자의 추천 점수를 재생성한다."""
    user = get_user(db, user_id)
    if user is None:
        return 0

    db.execute(delete(UserPreferenceScore).where(UserPreferenceScore.user_id == user_id))
    totals: dict[tuple[str, str], float] = defaultdict(float)
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    interaction_query = (
        select(UserMovieInteraction, Movie)
        .join(Movie, Movie.id == UserMovieInteraction.movie_id)
        .where(UserMovieInteraction.user_id == user_id)
    )
    if user.preference_learning_reset_at is not None:
        interaction_query = interaction_query.where(
            UserMovieInteraction.created_at >= user.preference_learning_reset_at
        )
    interactions = db.execute(
        interaction_query.order_by(UserMovieInteraction.created_at)
    ).all()
    seen_daily_actions = set()
    for interaction, movie in interactions:
        action_day = interaction.created_at.date() if interaction.created_at else None
        dedupe_key = (movie.id, interaction.action_type, action_day)
        if dedupe_key in seen_daily_actions:
            continue
        seen_daily_actions.add(dedupe_key)
        action_score = PREFERENCE_ACTION_SCORE.get(interaction.action_type)
        if action_score is None:
            continue
        interaction_time = interaction.created_at
        if interaction_time is None:
            decay = 1.0
        else:
            if interaction_time.tzinfo is None:
                interaction_time = interaction_time.replace(tzinfo=ZoneInfo("UTC"))
            age_days = max((now - interaction_time).total_seconds() / 86_400, 0.0)
            decay = 0.5 ** (age_days / PREFERENCE_HALF_LIFE_DAYS)
        for preference_type, weighted_values in core_movie_preference_items(movie).items():
            if not weighted_values:
                continue
            total_weight = sum(weight for _, weight in weighted_values)
            for value, value_weight in weighted_values:
                totals[(preference_type, value)] += (
                    action_score
                    * decay
                    * CORE_PREFERENCE_SHARES[preference_type]
                    * value_weight
                    / total_weight
                )

    for (preference_type, value), score in totals.items():
        db.add(UserPreferenceScore(
            user_id=user_id,
            preference_type=preference_type,
            preference_value=value,
            score=score,
            updated_at=now,
        ))
    db.flush()
    return len(totals)


def toggle_person_preference(
    db: Session,
    user_id: int,
    preference_type: str,
    preference_value: str,
) -> bool:
    """배우·감독 좋아요를 명시적 취향에 저장하고 전체 추천 점수를 재계산한다."""
    user = get_user(db, user_id)
    value = preference_value.strip()
    attribute_by_type = {
        "actor": "preferred_actors",
        "director": "preferred_directors",
    }
    attribute = attribute_by_type.get(preference_type)
    if user is None or attribute is None or not value:
        raise ValueError("저장할 인물 취향 정보가 올바르지 않습니다.")

    current_values = [
        item.strip()
        for item in (getattr(user, attribute) or [])
        if isinstance(item, str) and item.strip()
    ]
    is_liked = value not in current_values
    if is_liked:
        current_values.append(value)
    else:
        current_values = [item for item in current_values if item != value]

    setattr(user, attribute, list(dict.fromkeys(current_values)))
    if preference_type == "actor":
        rebuild_user_preference_scores(db, user.id)
    db.commit()
    db.refresh(user)
    return is_liked

# 사용자 취향 점수 하나 차감하는 함수
def decrease_user_preference_score(
        db : Session,
        user_id : int,
        preference_type : str,
        preference_value : str,
        score_delta : float,
):
    preference_type = preference_type.strip()
    preference_value = preference_value.strip()

    if preference_type not in PREFERENCE_TYPES:
        return False
    
    preference_score = db.scalar(
        select(UserPreferenceScore)
        .where(
            UserPreferenceScore.user_id == user_id,
            UserPreferenceScore.preference_type == preference_type,
            UserPreferenceScore.preference_value == preference_value
        )
    )
    #  과저 데이터에 취향 점수가 없는 경우
    if preference_score is None :
        return False
    
    remaining_score = (preference_score.score or 0.0) - score_delta

    # 점수가 0 이하가 되면 취향 점수 행을 삭제
    if remaining_score <= 0:
        db.delete(preference_score)
    else :
        preference_score.score = remaining_score

    return True

# 영화 한 편에서 발생했던 취향 점수 취소
def decrease_movie_preference_scores(
        db : Session,
        user_id : int,
        movie,
        action_type : str,
        action_count : int =1,
):
    if not action_type or action_count <= 0:
        return 0
    
    action_type = action_type.strip()

    if not action_type:
        return 0
    # like인 경우 2.0 반환
    action_score = PREFERENCE_ACTION_SCORE.get(action_type)

    if action_score is None :
        return 0
    
    decreased_count = 0

    for preference_type, weighted_values in core_movie_preference_items(movie).items():
        if not weighted_values:
            continue
        total_weight = sum(weight for _, weight in weighted_values)
        for preference_value, value_weight in weighted_values:
            score_delta = (
                action_score
                * action_count
                * CORE_PREFERENCE_SHARES[preference_type]
                * value_weight
                / total_weight
            )
            decreased = decrease_user_preference_score(
                db=db,
                user_id=user_id,
                preference_type=preference_type,
                preference_value=preference_value,
                score_delta=score_delta,
            )
            if decreased:
                decreased_count += 1

    return decreased_count

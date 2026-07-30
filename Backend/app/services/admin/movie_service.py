import json
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.actors import Actor, MovieActor
from app.models.admin import AdminAuditLog
from app.models.movies import Movie, MovieGenre, MovieStats
from app.models.users import User


def normalize_string_list(values: list[str] | None) -> list[str]:
    """장르, 배우, 키워드의 빈 값과 중복을 제거하고 입력 순서를 유지한다."""

    normalized_values = []

    for value in values or []:
        # 외부 API나 관리자 입력값에 포함된 앞뒤 공백을 제거해 동일한 값이
        # 서로 다른 장르·배우·키워드로 저장되는 것을 방지한다.
        normalized_value = value.strip()

        if (
            normalized_value
            and normalized_value not in normalized_values
        ):
            normalized_values.append(normalized_value)

    return normalized_values


# 관리자 API에서 사용하는 내부 movie_id로 영화 한 편을 조회한다.
def get_admin_movie(
    db: Session,
    movie_id: int,
) -> Movie | None:
    """내부 영화 ID에 해당하는 Movie 객체를 반환한다.

    Args:
        db: 영화를 조회할 SQLAlchemy 세션.
        movie_id: movies 테이블에서 사용하는 내부 기본키.

    Returns:
        영화가 존재하면 Movie 객체를 반환하고, 없으면 None을 반환한다.
    """

    # 관리자 영화 수정·삭제 API가 전달하는 movie_id는 TMDB에서 제공하는
    # tmdb_id가 아니라 movies 테이블의 내부 기본키이다.
    # 기본키 한 건 조회에 적합한 Session.get()을 사용한다.
    return db.get(Movie, movie_id)


def get_movie_by_tmdb_id(db: Session, tmdb_id: int) -> Movie | None:
    """TMDB 영화가 내부 movies 테이블에 이미 등록됐는지 조회한다."""

    return db.scalar(
        select(Movie)
        .where(Movie.tmdb_id == tmdb_id)
    )


def _datetime_to_iso(value: datetime | None) -> str | None:
    """관리자 API 응답에서 datetime을 JSON으로 전달할 ISO 문자열로 바꾼다."""

    return value.isoformat() if value is not None else None


def admin_movie_to_dict(movie: Movie) -> dict:
    """Movie ORM 객체를 관리자 API 응답과 감사 로그용 데이터로 변환한다."""

    return {
        "movie_id": movie.id,
        "tmdb_id": movie.tmdb_id,
        "title": movie.title,
        "overview": movie.overview,
        "genres": movie.genres or [],
        "director": movie.director,
        "cast": movie.cast or [],
        "keywords": movie.keywords or [],
        "year": movie.year,
        "language": movie.language,
        "vote_average": movie.vote_average,
        "vote_count": movie.vote_count,
        "audience_count": movie.audience_count,
        "poster_path": movie.poster_path,
        "last_synced_at": _datetime_to_iso(movie.last_synced_at),
        "created_at": _datetime_to_iso(movie.created_at),
        "updated_at": _datetime_to_iso(movie.updated_at),
    }


# movies.genres 배열과 movie_genres 테이블을 동일한 장르 목록으로 맞춘다.
def sync_admin_movie_genres(
    db: Session,
    movie: Movie,
    genres: list[str],
) -> bool:
    """영화 장르가 실제로 다를 때 두 장르 저장 위치를 함께 갱신한다.

    Args:
        db: 장르 배열과 장르 행을 같은 트랜잭션에서 처리할 DB 세션.
        movie: 장르를 등록하거나 수정할 Movie 객체.
        genres: 영화에 최종 저장할 장르 이름 목록.

    Returns:
        장르가 변경되거나 두 저장 위치의 불일치를 수정했으면 True,
        이미 동일한 상태라면 False를 반환한다.

    Notes:
        이 함수에서는 commit하지 않는다. 호출한 등록·수정 API가 영화의
        다른 데이터와 함께 commit하고, 실패하면 전체 rollback해야 한다.
    """

    # movie_genres.genre 컬럼은 최대 50자이므로 공백과 중복을 정리한 뒤
    # 길이를 맞추고 다시 중복을 제거해 배열과 장르 행의 값을 통일한다.
    normalized_genres = normalize_string_list(
        [
            genre[:50]
            for genre in normalize_string_list(genres)
        ]
    )
    current_movie_genres = normalize_string_list(movie.genres)

    # movies.genres 배열만 비교하면 movie_genres 행이 누락되거나 오래된
    # 상태를 발견할 수 없으므로 정규화 테이블의 실제 값도 함께 조회한다.
    stored_genres = list(
        db.scalars(
            select(MovieGenre.genre)
            .where(MovieGenre.movie_id == movie.id)
            .order_by(MovieGenre.id)
        ).all()
    )

    # 배열 컬럼과 정규화 테이블이 모두 최종 장르 목록과 같다면
    # 불필요한 UPDATE, DELETE와 INSERT를 실행하지 않는다.
    if (
        current_movie_genres == normalized_genres
        and stored_genres == normalized_genres
    ):
        return False

    # 영화 응답, 추천과 사용자 취향 처리에서 사용하는 배열 컬럼을 수정한다.
    movie.genres = normalized_genres

    # 장르 검색과 집계에서 사용하는 기존 movie_genres 행을 모두 제거한다.
    # 이후 최종 장르 목록으로 다시 생성해 배열과 행 데이터의 불일치도 복구한다.
    db.execute(
        delete(MovieGenre)
        .where(MovieGenre.movie_id == movie.id)
    )

    # 장르 하나당 하나의 행을 생성해 장르 검색에서 사용할 수 있게 한다.
    for genre in normalized_genres:
        db.add(
            MovieGenre(
                movie_id=movie.id,
                genre=genre,
            )
        )

    return True


def sync_admin_movie_actors(
    db: Session,
    movie: Movie,
    cast_credits: list[dict] | None,
) -> None:
    """TMDB 배우를 생성·갱신하고 새 영화와 배우의 출연 관계를 저장한다.

    Args:
        db: 영화와 배우 관계를 같은 트랜잭션에 추가할 SQLAlchemy 세션.
        movie: 내부 ID가 할당된 신규 Movie 객체.
        cast_credits: TMDB 상세 응답에서 변환한 배우 ID, 이름, 프로필,
            배역과 출연 순서 목록.

    Notes:
        배우마다 DB를 따로 조회하지 않고 TMDB 배우 ID 목록을 IN 조건으로
        한 번에 조회한다. 이 함수도 commit하지 않으며 영화 등록이 실패하면
        배우와 영화 관계까지 함께 rollback되도록 호출한 API에 맡긴다.
    """

    # 같은 배우가 TMDB 응답에 중복 포함된 경우 첫 번째 출연 정보만 사용해
    # movie_actors의 영화-배우 unique 제약 충돌을 방지한다.
    credit_by_tmdb_actor_id = {}

    for credit in cast_credits or []:
        if not isinstance(credit, dict):
            continue

        tmdb_actor_id = credit.get("tmdb_actor_id")
        actor_name = str(credit.get("name") or "").strip()

        if (
            not isinstance(tmdb_actor_id, int)
            or tmdb_actor_id <= 0
            or not actor_name
            or tmdb_actor_id in credit_by_tmdb_actor_id
        ):
            continue

        credit_by_tmdb_actor_id[tmdb_actor_id] = {
            **credit,
            "name": actor_name[:100],
        }

    if not credit_by_tmdb_actor_id:
        return

    tmdb_actor_ids = list(credit_by_tmdb_actor_id)

    # 기존 배우 확인을 한 번의 IN 쿼리로 처리해 출연진 수만큼 SELECT가
    # 반복되는 N+1 조회 문제를 피한다.
    existing_actors = db.scalars(
        select(Actor)
        .where(Actor.tmdb_actor_id.in_(tmdb_actor_ids))
    ).all()
    actor_by_tmdb_id = {
        actor.tmdb_actor_id: actor
        for actor in existing_actors
        if actor.tmdb_actor_id is not None
    }

    for tmdb_actor_id, credit in credit_by_tmdb_actor_id.items():
        actor = actor_by_tmdb_id.get(tmdb_actor_id)
        profile_path = credit.get("profile_path")

        if actor is None:
            # DB에 없는 배우만 새로 생성하고, 이후 관계 생성에서 내부 actor.id를
            # 사용할 수 있도록 딕셔너리에 함께 보관한다.
            actor = Actor(
                tmdb_actor_id=tmdb_actor_id,
                name=credit["name"],
                profile_path=(
                    str(profile_path)[:300]
                    if profile_path
                    else None
                ),
            )
            db.add(actor)
            actor_by_tmdb_id[tmdb_actor_id] = actor
        else:
            # TMDB의 최신 이름과 프로필을 반영하되, 새 응답에 프로필이 없으면
            # 기존에 저장된 유효한 프로필 경로를 지우지 않는다.
            actor.name = credit["name"]

            if profile_path:
                actor.profile_path = str(profile_path)[:300]

    # 새 배우들의 내부 PK를 한 번에 확보한 뒤 movie_actors 관계를 생성한다.
    db.flush()

    for tmdb_actor_id, credit in credit_by_tmdb_actor_id.items():
        actor = actor_by_tmdb_id[tmdb_actor_id]
        character_name = credit.get("character_name")
        cast_order = credit.get("cast_order")

        db.add(
            MovieActor(
                movie_id=movie.id,
                actor_id=actor.id,
                character_name=(
                    str(character_name).strip()[:150]
                    if character_name
                    else None
                ),
                cast_order=(
                    cast_order
                    if isinstance(cast_order, int)
                    else None
                ),
            )
        )


def create_admin_movie(
    db: Session,
    current_admin: User,
    movie_data: dict,
) -> Movie:
    """영화, 장르, 초기 통계와 관리자 감사 로그를 한 세션에 추가한다.

    Args:
        db: 관련 데이터를 하나의 트랜잭션으로 처리할 SQLAlchemy 세션.
        current_admin: 영화 등록 작업을 수행한 관리자 사용자.
        movie_data: Movie 모델의 컬럼 이름에 맞춘 영화 정보.

    Returns:
        DB 세션에 추가되고 내부 ID가 할당된 Movie 객체.

    Notes:
        이 함수에서는 commit하지 않는다. 호출하는 API에서 영화, 장르,
        통계와 감사 로그를 한 번에 commit해야 일부 데이터만 저장되는 것을
        막고, 실패 시 전체 rollback을 수행할 수 있다.
    """

    # 호출한 서비스가 전달한 원본 딕셔너리를 직접 변경하지 않도록 복사한다.
    data = movie_data.copy()

    tmdb_id = data.get("tmdb_id")

    # TMDB ID는 movies.tmdb_id에 unique 제약이 있으므로 서비스에서도 먼저
    # 확인해 DB 제약 오류보다 이해하기 쉬운 중복 메시지를 제공한다.
    if tmdb_id is not None:
        existing_movie = get_movie_by_tmdb_id(
            db=db,
            tmdb_id=tmdb_id,
        )

        if existing_movie is not None:
            raise ValueError("이미 등록된 TMDB 영화입니다.")

    # TMDB 등록에서만 전달되는 상세 배우 정보는 Movie 컬럼이 아니므로 먼저
    # 분리한다. 수동 등록처럼 값이 없는 경우에는 배우 관계 생성을 건너뛴다.
    cast_credits = data.pop("cast_credits", [])

    # 장르는 movies.genres 배열과 movie_genres 테이블에 함께 저장해야 하므로
    # Movie 객체를 만들기 전에 별도로 분리하고 값을 정리한다.
    genres = normalize_string_list(
        data.pop("genres", [])
    )

    # 배열 필드도 빈 문자열과 중복을 제거해 추천과 검색 결과의 품질을 유지한다.
    data["cast"] = normalize_string_list(data.get("cast"))
    data["keywords"] = normalize_string_list(data.get("keywords"))

    title = str(data.get("title") or "").strip()

    if not title:
        raise ValueError("영화 제목이 없습니다.")

    data["title"] = title[:300]

    # 예상하지 못한 키가 Movie 생성자에 전달되지 않도록 저장 가능한 컬럼만
    # 선택한다. 이후 수동 등록 요청 데이터도 이 함수를 안전하게 재사용한다.
    allowed_fields = {
        "tmdb_id",
        "title",
        "overview",
        "director",
        "cast",
        "keywords",
        "year",
        "language",
        "vote_average",
        "vote_count",
        "audience_count",
        "poster_path",
        "last_synced_at",
    }
    movie_fields = {
        key: value
        for key, value in data.items()
        if key in allowed_fields
    }

    # movies 테이블에 영화의 기본 정보를 추가한다. 장르는 내부 movie.id가
    # 필요한 movie_genres 행과 함께 아래 공통 동기화 함수에서 처리한다.
    movie = Movie(
        **movie_fields,
        genres=[],
    )
    db.add(movie)

    # movie_genres, movie_stats, 감사 로그는 생성된 movie.id가 필요하다.
    # flush는 SQL을 DB에 전달해 ID만 확보하며 최종 commit은 수행하지 않는다.
    db.flush()

    # 영화 응답·추천에서 사용하는 movies.genres 배열과 장르 검색에서
    # 사용하는 movie_genres 행을 공통 함수로 한 번에 생성한다.
    sync_admin_movie_genres(
        db=db,
        movie=movie,
        genres=genres,
    )

    # 새 영화의 조회, 검색 클릭, 좋아요와 랭킹 통계는 모두 0에서 시작한다.
    db.add(
        MovieStats(
            movie_id=movie.id,
            view_count=0,
            search_click_count=0,
            like_count=0,
            ranking_score=0,
        )
    )

    # TMDB 상세정보에 배우 ID가 포함된 경우 actors를 생성·갱신하고
    # movie_actors에 배역과 출연 순서를 저장한다.
    sync_admin_movie_actors(
        db=db,
        movie=movie,
        cast_credits=cast_credits,
    )

    # 누가 어떤 영화를 등록했는지 추적할 수 있도록 같은 트랜잭션에
    # 관리자 감사 로그를 추가한다. 영화 등록이 rollback되면 로그도 함께
    # rollback되어 실제 데이터와 감사 기록이 서로 어긋나지 않는다.
    db.add(
        AdminAuditLog(
            admin_user_id=current_admin.id,
            target_table="movies",
            target_id=movie.id,
            action="CREATE_MOVIE",
            before_data=None,
            after_data=json.dumps(
                admin_movie_to_dict(movie),
                ensure_ascii=False,
                default=str,
            ),
        )
    )

    return movie

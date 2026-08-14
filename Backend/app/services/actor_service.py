
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.actors import Actor, MovieActor
from app.models.movies import Movie


def _ranked_actor_statement():
    all_movie_credits = (
        select(
            MovieActor.actor_id.label("actor_id"),
            func.count(MovieActor.movie_id).label("movie_count"),
            func.sum(Movie.vote_count)
            .filter(MovieActor.cast_order <= 5)
            .label("top_billed_vote_count"),
        )
        .join(Movie, Movie.id == MovieActor.movie_id)
        .group_by(MovieActor.actor_id)
        .subquery()
    )
    korean_movie_credits = (
        select(
            MovieActor.actor_id.label("actor_id"),
            func.count(MovieActor.movie_id).label("korean_movie_count"),
        )
        .join(Movie, Movie.id == MovieActor.movie_id)
        .where(Movie.language == "ko")
        .group_by(MovieActor.actor_id)
        .subquery()
    )
    statement = (
        select(Actor)
        .outerjoin(
            all_movie_credits,
            all_movie_credits.c.actor_id == Actor.id,
        )
        .outerjoin(
            korean_movie_credits,
            korean_movie_credits.c.actor_id == Actor.id,
        )
    )

    return statement.order_by(
            # 별도 배우 인기도 컬럼이 없으므로 주연급 출연작의 TMDB 누적 투표 수를
            # 인지도 대체 지표로 사용하고 전체 출연 횟수와 한국어 영화 이력으로 보조 정렬한다.
            func.coalesce(all_movie_credits.c.top_billed_vote_count, 0).desc(),
            func.coalesce(all_movie_credits.c.movie_count, 0).desc(),
            func.coalesce(korean_movie_credits.c.korean_movie_count, 0).desc(),
            Actor.name.op("~")("[가-힣]").desc(),
            Actor.profile_path.is_(None),
            Actor.name,
            Actor.id,
        )


def _language_ranked_actor_statement(language: str):
    language_credits = (
        select(
            MovieActor.actor_id.label("actor_id"),
            func.count(MovieActor.movie_id).label("movie_count"),
            func.sum(Movie.vote_count)
            .filter(MovieActor.cast_order <= 5)
            .label("top_billed_vote_count"),
        )
        .join(Movie, Movie.id == MovieActor.movie_id)
        .where(Movie.language == language)
        .group_by(MovieActor.actor_id)
        .subquery()
    )
    return (
        select(Actor)
        .join(language_credits, language_credits.c.actor_id == Actor.id)
        .order_by(
            # 한 편에만 출연한 해외 배우가 지역 대표 목록을 차지하지 않도록
            # 해당 언어 영화의 출연작 수를 먼저 보고, 주연작 인지도로 보조한다.
            language_credits.c.movie_count.desc(),
            func.coalesce(language_credits.c.top_billed_vote_count, 0).desc(),
            Actor.profile_path.is_(None),
            Actor.name,
            Actor.id,
        )
    )


def get_actors_result(
    db: Session,
    query: str | None = None,
    page: int = 1,
    limit: int = 50,
):
    statement = _ranked_actor_statement()
    normalized_query = (query or "").strip()
    if normalized_query:
        pattern = f"%{normalized_query}%"
        statement = statement.where(or_(
            Actor.name.ilike(pattern),
            Actor.korean_name.ilike(pattern),
            Actor.original_name.ilike(pattern),
        ))

    statement = statement.offset((page - 1) * limit).limit(limit)
    return db.scalars(statement).all()


def get_onboarding_actors_result(db: Session):
    """온보딩 기본 배우를 출연 영화 언어 기준 8/4/12명으로 구성한다.

    배우 자체의 국적 데이터가 없으므로 한국어 영화 출연자를 먼저 한국 그룹에,
    남은 배우 중 일본어 영화 출연자를 일본 그룹에 배치한다. 마지막 그룹은 앞의
    두 그룹에 뽑히지 않은 영어권·기타 배우로 채운다.
    """
    korean = db.scalars(_language_ranked_actor_statement("ko").limit(8)).all()
    selected_ids = [actor.id for actor in korean]

    japanese_statement = _language_ranked_actor_statement("ja")
    if selected_ids:
        japanese_statement = japanese_statement.where(Actor.id.notin_(selected_ids))
    japanese = db.scalars(japanese_statement.limit(4)).all()
    selected_ids.extend(actor.id for actor in japanese)

    others_statement = _ranked_actor_statement()
    if selected_ids:
        others_statement = others_statement.where(Actor.id.notin_(selected_ids))
    others = db.scalars(others_statement.limit(12)).all()

    actors = [*korean, *japanese, *others]
    if len(actors) < 24:
        selected_ids = [actor.id for actor in actors]
        fill_statement = _ranked_actor_statement()
        if selected_ids:
            fill_statement = fill_statement.where(Actor.id.notin_(selected_ids))
        actors.extend(db.scalars(fill_statement.limit(24 - len(actors))).all())

    return actors

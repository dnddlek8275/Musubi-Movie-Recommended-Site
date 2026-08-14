from collections.abc import Iterable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.movies import Movie


def _as_positive_int(value) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def resolve_chat_movie(
    db: Session,
    *,
    movie_id=None,
    tmdb_id=None,
    title: str | None = None,
    year=None,
) -> Movie | None:
    """AI 추천 식별자를 서비스 내부 Movie 행으로 안전하게 연결한다."""
    internal_id = _as_positive_int(movie_id)
    if internal_id is not None:
        movie = db.get(Movie, internal_id)
        if movie is not None:
            return movie

    external_id = _as_positive_int(tmdb_id)
    if external_id is not None:
        movie = db.scalar(select(Movie).where(Movie.tmdb_id == external_id))
        if movie is not None:
            return movie

    normalized_title = str(title or "").strip()
    if not normalized_title:
        return None

    statement = select(Movie).where(func.lower(Movie.title) == normalized_title.lower())
    release_year = _as_positive_int(year)
    if release_year is not None:
        statement = statement.where(
            or_(Movie.year == release_year, func.extract("year", Movie.release_date) == release_year)
        )

    return db.scalar(
        statement.order_by(Movie.release_date.desc().nullslast(), Movie.id.desc()).limit(1)
    )


def enrich_recommended_movies(db: Session, movies: Iterable[dict] | None) -> list[dict]:
    """현재/과거 AI 응답에 내부 movie_id를 보강해 상세 페이지 링크를 만든다."""
    enriched: list[dict] = []
    for raw_movie in movies or []:
        if not isinstance(raw_movie, dict):
            continue
        movie = dict(raw_movie)
        linked = resolve_chat_movie(
            db,
            movie_id=movie.get("movie_id"),
            tmdb_id=movie.get("tmdb_id"),
            title=movie.get("title") or movie.get("name"),
            year=movie.get("year"),
        )
        if linked is not None:
            movie["movie_id"] = linked.id
            movie.setdefault("tmdb_id", linked.tmdb_id)
            movie.setdefault("title", linked.title)
            movie.setdefault("poster_path", linked.poster_path)
        enriched.append(movie)
    return enriched

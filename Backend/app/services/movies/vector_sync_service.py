from __future__ import annotations

from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.movies import Movie
from app.models.sync import MovieVectorSyncJob


def enqueue_movie_vector_sync(
    db: Session,
    *,
    tmdb_id: int,
    movie_id: int | None,
    operation: str,
) -> None:
    if operation not in {"upsert", "delete"}:
        raise ValueError("operation must be upsert or delete")
    statement = insert(MovieVectorSyncJob).values(
        tmdb_id=tmdb_id,
        movie_id=movie_id,
        operation=operation,
        status="pending",
        attempts=0,
        last_error=None,
        completed_at=None,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[MovieVectorSyncJob.tmdb_id],
        set_={
            "movie_id": statement.excluded.movie_id,
            "operation": statement.excluded.operation,
            "status": "pending",
            "attempts": 0,
            "last_error": None,
            "completed_at": None,
            "updated_at": datetime.now(timezone.utc),
        },
    )
    db.execute(statement)


def movie_vector_payload(movie: Movie) -> dict:
    return {
        "tmdb_id": movie.tmdb_id,
        "title": movie.title,
        "overview": movie.overview,
        "genres": movie.genres or [],
        "director": movie.director,
        "cast": movie.cast or [],
        "keywords": movie.keywords or [],
        "year": movie.year,
        "release_date": movie.release_date.isoformat() if movie.release_date else None,
        "runtime": movie.runtime,
        "production_countries": movie.production_countries or [],
        "certification": movie.certification,
        "certification_country": movie.certification_country,
        "language": movie.language,
        "vote_average": movie.vote_average,
        "vote_count": movie.vote_count,
        "audience_count": movie.audience_count,
        "poster_path": movie.poster_path,
    }


async def dispatch_pending_vector_jobs(db: Session, batch_size: int = 50) -> int:
    if not settings.AI_SYNC_TOKEN:
        return 0
    jobs = list(
        db.scalars(
            select(MovieVectorSyncJob)
            .where(MovieVectorSyncJob.status.in_(("pending", "failed")))
            .order_by(MovieVectorSyncJob.updated_at, MovieVectorSyncJob.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        ).all()
    )
    if not jobs:
        return 0

    movie_ids = [job.movie_id for job in jobs if job.operation == "upsert" and job.movie_id]
    movies = {
        movie.id: movie
        for movie in db.scalars(select(Movie).where(Movie.id.in_(movie_ids))).all()
    }
    upserts = []
    deletes = []
    valid_jobs = []
    for job in jobs:
        if job.operation == "delete":
            deletes.append(job.tmdb_id)
            valid_jobs.append(job)
            continue
        movie = movies.get(job.movie_id)
        if movie is None or movie.tmdb_id is None:
            job.status = "failed"
            job.attempts += 1
            job.last_error = "PostgreSQL movie row is missing"
            continue
        upserts.append(movie_vector_payload(movie))
        valid_jobs.append(job)

    if not valid_jobs:
        db.commit()
        return 0

    try:
        async with httpx.AsyncClient(timeout=settings.AI_SYNC_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{settings.AI_BASE_URL.rstrip('/')}/internal/movies/sync",
                headers={"Authorization": f"Bearer {settings.AI_SYNC_TOKEN}"},
                json={"upserts": upserts, "deletes": deletes},
            )
            response.raise_for_status()
    except Exception as error:
        message = str(error)[:1000]
        for job in valid_jobs:
            job.status = "failed"
            job.attempts += 1
            job.last_error = message
        db.commit()
        return 0

    completed_at = datetime.now(timezone.utc)
    for job in valid_jobs:
        job.status = "completed"
        job.attempts += 1
        job.last_error = None
        job.completed_at = completed_at
    db.commit()
    return len(valid_jobs)

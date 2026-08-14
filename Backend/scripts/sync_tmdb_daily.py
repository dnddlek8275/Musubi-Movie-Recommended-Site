#!/usr/bin/env python3
"""Incrementally synchronize qualified TMDB movies into PostgreSQL and Milvus."""

from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.dependencies import SessionLocal
from app.models.actors import MovieActor
from app.models.movies import Movie, MovieStats
from app.models.sync import TmdbDailySyncRun
from app.services.admin.movie_service import (
    normalize_string_list,
    sync_admin_movie_actors,
    sync_admin_movie_genres,
)
from app.services.admin.tmdb_register_service import (
    TmdbMovieNotFoundError,
    TmdbUnsafeMovieError,
    fetch_admin_tmdb_movie_detail,
)
from app.services.admin.tmdb_search_service import TMDB_BASE_URL
from app.services.movies.genre_relevance import sync_movie_genre_weights
from app.services.movies.tmdb_trailer_service import get_tmdb_auth
from app.services.movies.vector_sync_service import (
    dispatch_pending_vector_jobs,
    enqueue_movie_vector_sync,
)


MOVIE_COLUMNS = (
    "title", "overview", "director", "cast", "keywords", "year", "release_date",
    "runtime", "production_countries", "certification", "certification_country",
    "language", "vote_average", "vote_count", "poster_path",
    "last_synced_at",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-vector-dispatch", action="store_true")
    return parser.parse_args()


async def fetch_changed_ids(
    client: httpx.AsyncClient,
    auth_params: dict,
    target_date: date,
) -> set[int]:
    changed: set[int] = set()
    page = 1
    while True:
        response = await client.get(
            "/movie/changes",
            params={
                **auth_params,
                "start_date": target_date.isoformat(),
                "end_date": target_date.isoformat(),
                "page": page,
            },
        )
        response.raise_for_status()
        payload = response.json()
        for item in payload.get("results") or []:
            if isinstance(item, dict) and isinstance(item.get("id"), int):
                changed.add(item["id"])
        total_pages = min(int(payload.get("total_pages") or 1), 1000)
        if page >= total_pages:
            break
        page += 1
    return changed


async def discover_recent_qualified_ids(
    client: httpx.AsyncClient,
    auth_params: dict,
    target_date: date,
) -> set[int]:
    discovered: set[int] = set()
    start_date = target_date - timedelta(days=45)
    end_date = target_date + timedelta(days=365)
    for page in range(1, settings.TMDB_SYNC_DISCOVER_MAX_PAGES + 1):
        response = await client.get(
            "/discover/movie",
            params={
                **auth_params,
                "include_adult": "false",
                "include_video": "false",
                "language": "ko-KR",
                "sort_by": "popularity.desc",
                "vote_average.gte": settings.TMDB_SYNC_MIN_RATING,
                "vote_count.gte": settings.TMDB_SYNC_MIN_VOTES,
                "primary_release_date.gte": start_date.isoformat(),
                "primary_release_date.lte": end_date.isoformat(),
                "page": page,
            },
        )
        response.raise_for_status()
        payload = response.json()
        for item in payload.get("results") or []:
            if (
                isinstance(item, dict)
                and isinstance(item.get("id"), int)
                and item.get("adult") is False
                and item.get("poster_path")
            ):
                discovered.add(item["id"])
        total_pages = min(int(payload.get("total_pages") or 1), 500)
        if page >= total_pages:
            break
    return discovered


def _eligible_new_movie(data: dict) -> bool:
    return bool(
        data.get("poster_path")
        and float(data.get("vote_average") or 0) >= settings.TMDB_SYNC_MIN_RATING
        and int(data.get("vote_count") or 0) >= settings.TMDB_SYNC_MIN_VOTES
    )


def _save_movie(tmdb_id: int, data: dict) -> str:
    cast_credits = data.pop("cast_credits", [])
    genres = normalize_string_list(data.pop("genres", []))
    data["cast"] = normalize_string_list(data.get("cast"))
    data["keywords"] = normalize_string_list(data.get("keywords"))
    with SessionLocal.begin() as db:
        movie = db.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))
        action = "updated"
        if movie is None:
            if not _eligible_new_movie(data):
                return "skipped"
            movie = Movie(tmdb_id=tmdb_id, genres=[])
            db.add(movie)
            action = "imported"
        for column in MOVIE_COLUMNS:
            setattr(movie, column, data.get(column))
        if action == "imported":
            db.flush()
            db.add(MovieStats(movie_id=movie.id))
        sync_admin_movie_genres(db, movie, genres)
        sync_movie_genre_weights(db, movie)
        db.execute(delete(MovieActor).where(MovieActor.movie_id == movie.id))
        db.flush()
        sync_admin_movie_actors(db, movie, cast_credits)
        enqueue_movie_vector_sync(
            db,
            tmdb_id=tmdb_id,
            movie_id=movie.id,
            operation="upsert",
        )
        return action


def _delete_movie(tmdb_id: int) -> bool:
    with SessionLocal.begin() as db:
        movie = db.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))
        if movie is None:
            return False
        enqueue_movie_vector_sync(
            db,
            tmdb_id=tmdb_id,
            movie_id=None,
            operation="delete",
        )
        db.delete(movie)
        return True


async def run_sync(target_date: date, *, force: bool, dispatch_vectors: bool) -> dict:
    auth = get_tmdb_auth()
    if auth is None:
        raise RuntimeError("TMDB authentication is missing")
    state_db = SessionLocal()
    try:
        existing_run = state_db.get(TmdbDailySyncRun, target_date)
        if existing_run and existing_run.status == "completed" and not force:
            return {"status": "already_completed", "date": target_date.isoformat()}
        if existing_run and existing_run.status == "running" and not force:
            started_at = existing_run.started_at
            if started_at and datetime.now(timezone.utc) - started_at < timedelta(hours=3):
                return {"status": "already_running", "date": target_date.isoformat()}
        if existing_run is None:
            existing_run = TmdbDailySyncRun(sync_date=target_date)
            state_db.add(existing_run)
        existing_run.status = "running"
        existing_run.last_error = None
        existing_run.started_at = datetime.now(timezone.utc)
        existing_run.completed_at = None
        state_db.commit()

        headers, auth_params = auth
        async with httpx.AsyncClient(base_url=TMDB_BASE_URL, headers=headers, timeout=30.0) as client:
            changed_ids = await fetch_changed_ids(client, auth_params, target_date)
            discovered_ids = await discover_recent_qualified_ids(client, auth_params, target_date)

        with SessionLocal() as db:
            existing_ids = set(
                db.scalars(select(Movie.tmdb_id).where(Movie.tmdb_id.in_(changed_ids))).all()
            )
        target_ids = sorted(existing_ids | discovered_ids)
        counts = {"imported": 0, "updated": 0, "deleted": 0, "failed": 0, "skipped": 0}
        concurrency = max(1, min(settings.TMDB_SYNC_FETCH_CONCURRENCY, 10))
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_one(tmdb_id: int):
            async with semaphore:
                try:
                    return tmdb_id, await fetch_admin_tmdb_movie_detail(tmdb_id), None
                except Exception as error:
                    return tmdb_id, None, error

        for start in range(0, len(target_ids), 50):
            results = await asyncio.gather(
                *(fetch_one(tmdb_id) for tmdb_id in target_ids[start : start + 50])
            )
            for tmdb_id, data, error in results:
                if isinstance(error, (TmdbUnsafeMovieError, TmdbMovieNotFoundError)):
                    counts["deleted"] += int(_delete_movie(tmdb_id))
                elif error is not None:
                    counts["failed"] += 1
                    print(f"TMDB {tmdb_id} failed: {error}", flush=True)
                else:
                    try:
                        result = _save_movie(tmdb_id, data)
                        counts[result] += 1
                    except Exception as save_error:
                        counts["failed"] += 1
                        print(f"TMDB {tmdb_id} save failed: {save_error}", flush=True)

        dispatched = 0
        if dispatch_vectors:
            while True:
                with SessionLocal() as db:
                    completed = await dispatch_pending_vector_jobs(db)
                if completed == 0:
                    break
                dispatched += completed

        with SessionLocal.begin() as db:
            run = db.get(TmdbDailySyncRun, target_date)
            run.status = "completed" if counts["failed"] == 0 else "partial"
            run.changed_count = len(target_ids)
            run.imported_count = counts["imported"]
            run.updated_count = counts["updated"]
            run.deleted_count = counts["deleted"]
            run.failed_count = counts["failed"]
            run.completed_at = datetime.now(timezone.utc)
        return {"date": target_date.isoformat(), **counts, "vector_jobs_completed": dispatched}
    except Exception as error:
        state_db.rollback()
        run = state_db.get(TmdbDailySyncRun, target_date)
        if run:
            run.status = "failed"
            run.last_error = str(error)[:2000]
            run.completed_at = datetime.now(timezone.utc)
            state_db.commit()
        raise
    finally:
        state_db.close()


async def main() -> None:
    args = parse_args()
    result = await run_sync(
        args.date,
        force=args.force,
        dispatch_vectors=not args.skip_vector_dispatch,
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())

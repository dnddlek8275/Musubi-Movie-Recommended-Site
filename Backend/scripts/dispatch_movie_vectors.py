from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from app.core.dependencies import SessionLocal
from app.models.sync import MovieVectorSyncJob
from app.services.movies.vector_sync_service import dispatch_pending_vector_jobs


async def main() -> None:
    completed_total = 0
    batches = 0

    while True:
        with SessionLocal() as db:
            completed = await dispatch_pending_vector_jobs(db)
        if completed == 0:
            break
        completed_total += completed
        batches += 1
        if batches >= 200:
            raise RuntimeError("movie vector dispatch exceeded 200 batches")

    with SessionLocal() as db:
        remaining = db.scalar(
            select(func.count(MovieVectorSyncJob.id)).where(
                MovieVectorSyncJob.status.in_(("pending", "failed"))
            )
        )

    if remaining:
        raise RuntimeError(f"movie vector sync jobs remain: {remaining}")
    print(f"movie vector sync completed: {completed_total}")


if __name__ == "__main__":
    asyncio.run(main())

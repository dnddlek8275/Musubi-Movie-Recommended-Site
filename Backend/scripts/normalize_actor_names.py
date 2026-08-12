from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

import httpx
from sqlalchemy import func, or_, select, update

from app.core.dependencies import SessionLocal
from app.models.actors import Actor, MovieActor
from app.models.movies import Movie
from app.models.users import User
from app.services.actor_name_policy import (
    actor_display_name,
    infer_is_korean,
    resolved_actor_name,
    select_korean_name,
)
from app.services.movies.tmdb_trailer_service import TMDB_BASE_URL, get_tmdb_auth
from app.services.movies.vector_sync_service import enqueue_movie_vector_sync


@dataclass(frozen=True)
class ActorTarget:
    actor_id: int
    tmdb_actor_id: int
    current_name: str
    korean_credit_count: int
    total_credit_count: int


@dataclass(frozen=True)
class ActorResolution:
    target: ActorTarget
    original_name: str | None
    korean_name: str | None
    is_korean: bool | None
    display_name: str | None
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TMDB 근거로 한국 배우는 한글명, 외국 배우는 원문명으로 정규화합니다."
    )
    parser.add_argument("--apply", action="store_true", help="검토 결과를 DB에 반영합니다.")
    parser.add_argument("--limit", type=int, default=200, help="한 번에 확인할 배우 수입니다.")
    parser.add_argument("--offset", type=int, default=0, help="재개할 배우 오프셋입니다.")
    parser.add_argument("--concurrency", type=int, default=8, help="TMDB 동시 요청 수입니다.")
    parser.add_argument("--actor-id", type=int, action="append", default=[])
    return parser.parse_args()


def load_targets(args: argparse.Namespace) -> list[ActorTarget]:
    credit_stats = (
        select(
            MovieActor.actor_id.label("actor_id"),
            func.count(MovieActor.movie_id).label("total_credit_count"),
            func.count(MovieActor.movie_id)
            .filter(or_(Movie.language == "ko", Movie.production_countries.contains(["KR"])))
            .label("korean_credit_count"),
        )
        .join(Movie, Movie.id == MovieActor.movie_id)
        .group_by(MovieActor.actor_id)
        .subquery()
    )
    statement = (
        select(
            Actor.id,
            Actor.tmdb_actor_id,
            Actor.name,
            func.coalesce(credit_stats.c.korean_credit_count, 0),
            func.coalesce(credit_stats.c.total_credit_count, 0),
        )
        .outerjoin(credit_stats, credit_stats.c.actor_id == Actor.id)
        .where(Actor.tmdb_actor_id.is_not(None))
        .order_by(Actor.id)
    )
    if args.actor_id:
        statement = statement.where(Actor.id.in_(args.actor_id))
    else:
        statement = statement.offset(max(args.offset, 0)).limit(max(args.limit, 1))
    with SessionLocal() as db:
        return [
            ActorTarget(
                actor_id=row[0],
                tmdb_actor_id=row[1],
                current_name=row[2],
                korean_credit_count=int(row[3]),
                total_credit_count=int(row[4]),
            )
            for row in db.execute(statement).all()
        ]


async def resolve_target(
    client: httpx.AsyncClient,
    auth_params: dict[str, str],
    semaphore: asyncio.Semaphore,
    target: ActorTarget,
) -> ActorResolution:
    try:
        async with semaphore:
            korean_response, original_response = await asyncio.gather(
                client.get(f"/person/{target.tmdb_actor_id}", params={**auth_params, "language": "ko-KR"}),
                client.get(f"/person/{target.tmdb_actor_id}", params={**auth_params, "language": "en-US"}),
            )
        korean_response.raise_for_status()
        original_response.raise_for_status()
        korean_payload = korean_response.json()
        original_payload = original_response.json()
        original_name = str(original_payload.get("name") or "").strip()[:100] or None
        korean_name = select_korean_name(
            korean_payload.get("name"),
            [
                *(korean_payload.get("also_known_as") or []),
                *(original_payload.get("also_known_as") or []),
            ],
        )
        is_korean = infer_is_korean(
            place_of_birth=original_payload.get("place_of_birth"),
            korean_name=korean_name,
            korean_credit_count=target.korean_credit_count,
            total_credit_count=target.total_credit_count,
        )
        display_name = resolved_actor_name(
            current_name=target.current_name,
            original_name=original_name,
            korean_name=korean_name,
            is_korean=is_korean,
        )
        return ActorResolution(target, original_name, korean_name, is_korean, display_name)
    except Exception as error:
        return ActorResolution(target, None, None, None, None, str(error)[:300])


async def resolve_targets(
    targets: list[ActorTarget],
    concurrency: int,
) -> list[ActorResolution]:
    auth = get_tmdb_auth()
    if auth is None:
        raise RuntimeError("TMDB 인증 정보가 설정되지 않았습니다.")
    headers, auth_params = auth
    semaphore = asyncio.Semaphore(max(concurrency, 1))
    async with httpx.AsyncClient(base_url=TMDB_BASE_URL, headers=headers, timeout=15.0) as client:
        return await asyncio.gather(*[
            resolve_target(client, auth_params, semaphore, target)
            for target in targets
        ])


def apply_resolutions(resolutions: list[ActorResolution]) -> dict[str, int]:
    changed_actor_ids: list[int] = []
    renamed: list[tuple[str, str]] = []
    with SessionLocal.begin() as db:
        for resolution in resolutions:
            if resolution.error:
                continue
            actor = db.get(Actor, resolution.target.actor_id)
            if actor is None:
                continue
            actor.original_name = resolution.original_name
            actor.korean_name = resolution.korean_name
            actor.is_korean = resolution.is_korean
            next_name = resolution.display_name or actor.name
            if next_name != actor.name:
                renamed.append((actor.name, next_name))
                actor.name = next_name
                changed_actor_ids.append(actor.id)

        if not changed_actor_ids:
            return {"renamed_actors": 0, "updated_movies": 0}

        db.flush()
        movie_ids = list(db.scalars(
            select(MovieActor.movie_id)
            .where(MovieActor.actor_id.in_(changed_actor_ids))
            .distinct()
        ).all())
        for movie_id in movie_ids:
            movie = db.get(Movie, movie_id)
            if movie is None:
                continue
            actors = db.scalars(
                select(Actor)
                .join(MovieActor, MovieActor.actor_id == Actor.id)
                .where(MovieActor.movie_id == movie_id)
                .order_by(MovieActor.cast_order.asc().nullslast(), MovieActor.id.asc())
            ).all()
            movie.cast = [actor_display_name(actor) for actor in actors]
            if movie.tmdb_id:
                enqueue_movie_vector_sync(
                    db,
                    tmdb_id=movie.tmdb_id,
                    movie_id=movie.id,
                    operation="upsert",
                )

        # 사용자 취향은 현재 이름 문자열로 저장되므로 이름 변경과 함께 보존한다.
        for old_name, new_name in renamed:
            db.execute(
                update(User)
                .where(User.preferred_actors.any(old_name))
                .values(preferred_actors=func.array_replace(User.preferred_actors, old_name, new_name))
            )
        return {"renamed_actors": len(changed_actor_ids), "updated_movies": len(movie_ids)}


async def main() -> None:
    args = parse_args()
    targets = load_targets(args)
    resolutions = await resolve_targets(targets, args.concurrency)
    for item in resolutions:
        status = "error" if item.error else "resolved" if item.is_korean is not None else "review"
        print(
            "|".join([
                status,
                str(item.target.actor_id),
                str(item.target.tmdb_actor_id),
                item.target.current_name,
                item.display_name or "",
                "KR" if item.is_korean is True else "FOREIGN" if item.is_korean is False else "UNKNOWN",
                item.error or "",
            ])
        )
    if args.apply:
        print(apply_resolutions(resolutions))
    else:
        print("dry-run: --apply를 지정하지 않아 DB를 변경하지 않았습니다.")


if __name__ == "__main__":
    asyncio.run(main())

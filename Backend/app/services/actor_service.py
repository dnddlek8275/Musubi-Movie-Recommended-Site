
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.actors import Actor


def get_actors_result(
    db: Session,
    query: str | None = None,
    page: int = 1,
    limit: int = 50,
):
    statement = select(Actor)

    normalized_query = (query or "").strip()
    if normalized_query:
        statement = statement.where(
            Actor.name.ilike(f"%{normalized_query}%")
        )

    statement = (
        statement
        .order_by(
            Actor.profile_path.is_(None),
            Actor.name,
            Actor.id,
        )
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return db.scalars(statement).all()

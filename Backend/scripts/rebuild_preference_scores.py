#!/usr/bin/env python3
"""Rebuild learned preference scores from deduplicated local interaction history."""

from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.dependencies import SessionLocal
from app.models.users import User
from app.services.preference_service import rebuild_user_preference_scores


LOCAL_DB_HOSTS = {"db", "localhost", "127.0.0.1", "::1"}


def main() -> None:
    host = make_url(settings.DATABASE_URL).host
    if host not in LOCAL_DB_HOSTS:
        raise SystemExit(f"Refusing to update non-local DB host {host!r}.")
    with SessionLocal.begin() as session:
        user_ids = list(session.scalars(select(User.id).order_by(User.id)))
        for user_id in user_ids:
            count = rebuild_user_preference_scores(session, user_id)
            print(f"user_id={user_id} preference_scores={count}")


if __name__ == "__main__":
    main()

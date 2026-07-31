import argparse
import sys

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from app.core.config import settings


def load_history() -> tuple[ScriptDirectory, tuple[str, ...]]:
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    heads = tuple(script.get_heads())

    if len(heads) != 1:
        raise RuntimeError(
            f"Alembic head는 정확히 하나여야 합니다. 현재 heads: {heads}"
        )

    return script, heads


def validate_database_url() -> None:
    url = make_url(settings.DATABASE_URL)

    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("Migration DATABASE_URL은 PostgreSQL이어야 합니다.")

    if not url.host:
        raise RuntimeError("Migration DATABASE_URL에 DB host가 없습니다.")


def validate_known_revisions(
    script: ScriptDirectory,
    current_heads: tuple[str, ...],
) -> None:
    for revision in current_heads:
        if script.get_revision(revision) is None:
            raise RuntimeError(
                f"DB에 저장소가 알지 못하는 Alembic revision이 있습니다: {revision}"
            )


def validate_before_migration() -> None:
    script, target_heads = load_history()
    validate_database_url()

    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        connect_args={"connect_timeout": 5},
    )

    with engine.connect() as connection:
        current_heads = tuple(
            MigrationContext.configure(connection).get_current_heads()
        )
        validate_known_revisions(script, current_heads)

        pgcrypto_installed = connection.scalar(
            text(
                "SELECT EXISTS ("
                "SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto'"
                ")"
            )
        )
        if not pgcrypto_installed:
            raise RuntimeError(
                "pgcrypto extension이 없습니다. "
                "관리자가 운영 DB에 먼저 설치해야 합니다."
            )

        can_create_schema_objects = connection.scalar(
            text(
                "SELECT has_schema_privilege("
                "current_user, current_schema(), 'CREATE'"
                ")"
            )
        )
        if not can_create_schema_objects:
            raise RuntimeError(
                "Migration 계정에 현재 schema의 CREATE 권한이 없습니다."
            )

    print(
        "Migration preflight passed: "
        f"current={current_heads or ('base',)}, target={target_heads}"
    )


def validate_after_migration() -> None:
    _, target_heads = load_history()
    validate_database_url()

    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        connect_args={"connect_timeout": 5},
    )

    with engine.connect() as connection:
        current_heads = tuple(
            MigrationContext.configure(connection).get_current_heads()
        )

    if set(current_heads) != set(target_heads):
        raise RuntimeError(
            "Migration 후 DB revision이 head와 일치하지 않습니다. "
            f"current={current_heads}, target={target_heads}"
        )

    print(f"Migration verification passed: current={current_heads}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=("history", "before", "after"),
        required=True,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        if args.phase == "history":
            _, heads = load_history()
            print(f"Alembic history passed: head={heads[0]}")
        elif args.phase == "before":
            validate_before_migration()
        else:
            validate_after_migration()
    except Exception as exc:
        print(f"Migration validation failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

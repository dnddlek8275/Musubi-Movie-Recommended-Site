"""add movie search indexes

Revision ID: 20260806_0020
Revises: 20260806_0019
"""

from alembic import op


revision = "20260806_0020"
down_revision = "20260806_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_movies_title_trgm "
        "ON movies USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_movies_overview_trgm "
        "ON movies USING gin (overview gin_trgm_ops) WHERE overview IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_movies_director_trgm "
        "ON movies USING gin (director gin_trgm_ops) WHERE director IS NOT NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_movies_genres_gin ON movies USING gin (genres)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_movies_keywords_gin ON movies USING gin (keywords)")
    op.execute('CREATE INDEX IF NOT EXISTS ix_movies_cast_gin ON movies USING gin ("cast")')
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_movies_production_countries_gin "
        "ON movies USING gin (production_countries)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_movies_production_countries_gin")
    op.execute("DROP INDEX IF EXISTS ix_movies_cast_gin")
    op.execute("DROP INDEX IF EXISTS ix_movies_keywords_gin")
    op.execute("DROP INDEX IF EXISTS ix_movies_genres_gin")
    op.execute("DROP INDEX IF EXISTS ix_movies_director_trgm")
    op.execute("DROP INDEX IF EXISTS ix_movies_overview_trgm")
    op.execute("DROP INDEX IF EXISTS ix_movies_title_trgm")

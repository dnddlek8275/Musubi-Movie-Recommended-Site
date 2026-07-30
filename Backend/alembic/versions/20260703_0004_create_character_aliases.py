"""create character aliases

Revision ID: 20260703_0004
Revises: 20260703_0003
Create Date: 2026-07-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260703_0004"
down_revision: str | None = "20260703_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # character_aliases: 자유 대화에서 언급된 별칭을 정식 캐릭터 이름으로 매핑한다.
    # 캐릭터가 삭제되면 해당 캐릭터의 별칭도 함께 삭제되어 고아 별칭이 남지 않는다.
    op.create_table(
        "character_aliases",
        # id: 캐릭터 별칭 행을 식별하는 내부 기본키.
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # character_id: 별칭이 연결된 characters.id. 캐릭터 삭제 시 별칭도 삭제된다.
        sa.Column("character_id", sa.BigInteger(), nullable=False),
        # alias: 사용자가 메시지에서 부를 수 있는 캐릭터 별칭.
        sa.Column("alias", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
    )
    # 캐릭터별 별칭 조회와 별칭 기반 캐릭터 매핑을 빠르게 하기 위한 인덱스.
    op.create_index("ix_character_aliases_character_id", "character_aliases", ["character_id"])
    op.create_index("ix_character_aliases_alias", "character_aliases", ["alias"], unique=True)


def downgrade() -> None:
    # 캐릭터 별칭 테이블과 조회용 인덱스를 제거한다.
    op.drop_index("ix_character_aliases_alias", table_name="character_aliases")
    op.drop_index("ix_character_aliases_character_id", table_name="character_aliases")
    op.drop_table("character_aliases")

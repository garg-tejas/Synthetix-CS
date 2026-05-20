"""fix document_chunks created_at server default

Revision ID: g9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-05-20 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "g9b0c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add server-side default so raw psycopg INSERTs don't need to supply created_at
    op.alter_column(
        "document_chunks",
        "created_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "document_chunks",
        "created_at",
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )

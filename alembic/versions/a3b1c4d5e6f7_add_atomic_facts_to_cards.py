"""add atomic_facts to cards

Revision ID: a3b1c4d5e6f7
Revises: 7f2d3a7c2b11
Create Date: 2026-03-12 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3b1c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "7f2d3a7c2b11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add atomic_facts JSON column to cards table."""
    op.add_column("cards", sa.Column("atomic_facts", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove atomic_facts column from cards table."""
    op.drop_column("cards", "atomic_facts")

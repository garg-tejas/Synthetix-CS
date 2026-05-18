"""add clerk_user_id to users and document_chunks table

Revision ID: d1e2f3a4b5c6
Revises: c5d3e7f8a1b2
Create Date: 2026-05-18 20:50:07.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c5d3e7f8a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add Clerk columns to users
    op.add_column('users', sa.Column('clerk_user_id', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('display_name', sa.String(length=128), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.Text(), nullable=True))
    op.create_index(op.f('ix_users_clerk_user_id'), 'users', ['clerk_user_id'], unique=True)

    # Document chunks table (for pgvector persistence)
    op.create_table('document_chunks',
        sa.Column('id', sa.String(length=128), nullable=False),
        sa.Column('book_id', sa.String(length=64), nullable=False),
        sa.Column('header_path', sa.Text(), nullable=False),
        sa.Column('chunk_type', sa.String(length=32), nullable=False),
        sa.Column('key_terms', sa.JSON(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('potential_questions', sa.JSON(), nullable=True),
        sa.Column('subject', sa.String(length=32), nullable=True),
        sa.Column('embedding_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_chunks_book_id'), 'document_chunks', ['book_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_subject'), 'document_chunks', ['subject'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_document_chunks_subject'), table_name='document_chunks')
    op.drop_index(op.f('ix_document_chunks_book_id'), table_name='document_chunks')
    op.drop_table('document_chunks')
    op.drop_index(op.f('ix_users_clerk_user_id'), table_name='users')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'display_name')
    op.drop_column('users', 'clerk_user_id')

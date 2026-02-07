"""add learning path and swot foundation

Revision ID: 7f2d3a7c2b11
Revises: e9ec022a3d0d
Create Date: 2026-02-07 16:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f2d3a7c2b11"
down_revision: Union[str, Sequence[str], None] = "e9ec022a3d0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("cards", sa.Column("topic_key", sa.String(length=128), nullable=True))
    op.add_column("cards", sa.Column("variant_of_card_id", sa.Integer(), nullable=True))
    op.add_column(
        "cards",
        sa.Column("generation_origin", sa.String(length=32), server_default="seed", nullable=False),
    )
    op.add_column("cards", sa.Column("provenance_json", sa.JSON(), nullable=True))
    op.create_index("ix_cards_topic_key", "cards", ["topic_key"], unique=False)
    op.create_index("ix_cards_variant_of_card_id", "cards", ["variant_of_card_id"], unique=False)
    op.create_foreign_key(
        "fk_cards_variant_of_card_id_cards",
        "cards",
        "cards",
        ["variant_of_card_id"],
        ["id"],
    )

    op.add_column("review_attempts", sa.Column("served_card_id", sa.Integer(), nullable=True))
    op.create_index("ix_review_attempts_served_card_id", "review_attempts", ["served_card_id"], unique=False)
    op.create_foreign_key(
        "fk_review_attempts_served_card_id_cards",
        "review_attempts",
        "cards",
        ["served_card_id"],
        ["id"],
    )

    op.create_table(
        "topic_taxonomy_nodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("topic_key", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("parent_topic_key", sa.String(length=128), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject", "topic_key", name="uq_topic_taxonomy_subject_key"),
    )
    op.create_index("ix_topic_taxonomy_nodes_subject", "topic_taxonomy_nodes", ["subject"], unique=False)
    op.create_index("ix_topic_taxonomy_nodes_topic_key", "topic_taxonomy_nodes", ["topic_key"], unique=False)

    op.create_table(
        "topic_prerequisites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("topic_key", sa.String(length=128), nullable=False),
        sa.Column("prerequisite_key", sa.String(length=128), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subject",
            "topic_key",
            "prerequisite_key",
            name="uq_topic_prereq_subject_topic_prereq",
        ),
    )
    op.create_index("ix_topic_prerequisites_subject", "topic_prerequisites", ["subject"], unique=False)
    op.create_index("ix_topic_prerequisites_topic_key", "topic_prerequisites", ["topic_key"], unique=False)
    op.create_index(
        "ix_topic_prerequisites_prerequisite_key",
        "topic_prerequisites",
        ["prerequisite_key"],
        unique=False,
    )

    op.create_table(
        "user_topic_mastery",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("topic_key", sa.String(length=128), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("avg_quality", sa.Float(), nullable=False),
        sa.Column("due_count", sa.Integer(), nullable=False),
        sa.Column("overdue_count", sa.Integer(), nullable=False),
        sa.Column("lapse_count", sa.Integer(), nullable=False),
        sa.Column("recent_trend", sa.Float(), nullable=False),
        sa.Column("mastery_score", sa.Float(), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "subject", "topic_key", name="uq_user_topic_mastery"),
    )
    op.create_index("ix_user_topic_mastery_user_id", "user_topic_mastery", ["user_id"], unique=False)
    op.create_index("ix_user_topic_mastery_subject", "user_topic_mastery", ["subject"], unique=False)
    op.create_index("ix_user_topic_mastery_topic_key", "user_topic_mastery", ["topic_key"], unique=False)

    op.create_table(
        "user_topic_swot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("topic_key", sa.String(length=128), nullable=False),
        sa.Column("strength_score", sa.Float(), nullable=False),
        sa.Column("weakness_score", sa.Float(), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("threat_score", sa.Float(), nullable=False),
        sa.Column("primary_bucket", sa.String(length=16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "subject", "topic_key", name="uq_user_topic_swot"),
    )
    op.create_index("ix_user_topic_swot_user_id", "user_topic_swot", ["user_id"], unique=False)
    op.create_index("ix_user_topic_swot_subject", "user_topic_swot", ["subject"], unique=False)
    op.create_index("ix_user_topic_swot_topic_key", "user_topic_swot", ["topic_key"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_user_topic_swot_topic_key", table_name="user_topic_swot")
    op.drop_index("ix_user_topic_swot_subject", table_name="user_topic_swot")
    op.drop_index("ix_user_topic_swot_user_id", table_name="user_topic_swot")
    op.drop_table("user_topic_swot")

    op.drop_index("ix_user_topic_mastery_topic_key", table_name="user_topic_mastery")
    op.drop_index("ix_user_topic_mastery_subject", table_name="user_topic_mastery")
    op.drop_index("ix_user_topic_mastery_user_id", table_name="user_topic_mastery")
    op.drop_table("user_topic_mastery")

    op.drop_index("ix_topic_prerequisites_prerequisite_key", table_name="topic_prerequisites")
    op.drop_index("ix_topic_prerequisites_topic_key", table_name="topic_prerequisites")
    op.drop_index("ix_topic_prerequisites_subject", table_name="topic_prerequisites")
    op.drop_table("topic_prerequisites")

    op.drop_index("ix_topic_taxonomy_nodes_topic_key", table_name="topic_taxonomy_nodes")
    op.drop_index("ix_topic_taxonomy_nodes_subject", table_name="topic_taxonomy_nodes")
    op.drop_table("topic_taxonomy_nodes")

    op.drop_constraint(
        "fk_review_attempts_served_card_id_cards",
        "review_attempts",
        type_="foreignkey",
    )
    op.drop_index("ix_review_attempts_served_card_id", table_name="review_attempts")
    op.drop_column("review_attempts", "served_card_id")

    op.drop_constraint(
        "fk_cards_variant_of_card_id_cards",
        "cards",
        type_="foreignkey",
    )
    op.drop_index("ix_cards_variant_of_card_id", table_name="cards")
    op.drop_index("ix_cards_topic_key", table_name="cards")
    op.drop_column("cards", "provenance_json")
    op.drop_column("cards", "generation_origin")
    op.drop_column("cards", "variant_of_card_id")
    op.drop_column("cards", "topic_key")

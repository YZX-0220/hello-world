"""add cultural guidances and prompt templates tables

Revision ID: 7b8c9d0e1f2a
Revises: f7a8b9c0d1e2
Create Date: 2026-11-12 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b8c9d0e1f2a"
down_revision: str | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cultural_guidances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=False),
        sa.Column("taboo", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_cultural_guidances_code", "cultural_guidances", ["code"], unique=True)
    op.create_index(
        "ix_cultural_guidances_sort_order", "cultural_guidances", ["sort_order"], unique=False
    )
    op.create_index(
        "ix_cultural_guidances_is_enabled", "cultural_guidances", ["is_enabled"], unique=False
    )

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("scope", sa.String(length=16), nullable=False, server_default="user"),
        sa.Column("category", sa.String(length=32), nullable=False, server_default="positive"),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("variables_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prompt_templates_user_id", "prompt_templates", ["user_id"], unique=False)
    op.create_index("ix_prompt_templates_code", "prompt_templates", ["code"], unique=False)
    op.create_index("ix_prompt_templates_scope", "prompt_templates", ["scope"], unique=False)
    op.create_index("ix_prompt_templates_category", "prompt_templates", ["category"], unique=False)
    op.create_index("ix_prompt_templates_status", "prompt_templates", ["status"], unique=False)

    op.create_table(
        "prompt_template_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("variables_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("change_note", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["prompt_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "version", name="uq_prompt_template_version"),
    )
    op.create_index(
        "ix_prompt_template_versions_template_id",
        "prompt_template_versions",
        ["template_id"],
        unique=False,
    )
    op.create_index(
        "ix_prompt_template_version_query",
        "prompt_template_versions",
        ["template_id", "version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("prompt_template_versions")
    op.drop_table("prompt_templates")
    op.drop_table("cultural_guidances")

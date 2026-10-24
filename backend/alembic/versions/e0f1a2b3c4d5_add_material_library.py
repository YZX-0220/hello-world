"""Add shared material library.

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
"""

import sqlalchemy as sa
from alembic import op

revision = "e0f1a2b3c4d5"
down_revision = "d9e0f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "material_library_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("video_asset_id", sa.String(), nullable=False),
        sa.Column("cover_asset_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["video_asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cover_asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("status IN ('draft', 'published', 'deleted')", name="ck_library_status"),
        sa.CheckConstraint("version >= 1", name="ck_library_version"),
    )
    for column in ("model_name", "video_asset_id", "cover_asset_id"):
        op.create_index(f"ix_material_library_items_{column}", "material_library_items", [column])
    op.create_index(
        "ix_library_status_created", "material_library_items", ["status", "created_at", "id"]
    )


def downgrade() -> None:
    op.drop_table("material_library_items")

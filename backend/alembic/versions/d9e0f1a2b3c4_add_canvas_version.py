"""Add independent canvas version for concurrent editing.

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
"""

import sqlalchemy as sa
from alembic import op

revision = "d9e0f1a2b3c4"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "video_projects",
        sa.Column("canvas_version", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("video_projects", "canvas_version")

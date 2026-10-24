"""add canvas_data to video_projects

Revision ID: c8d9e0f1a2b3
Revises: b7c1d2e3f4a5
Create Date: 2026-10-11

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c8d9e0f1a2b3"
down_revision = "b7c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite 加可空列无需重建表
    op.add_column("video_projects", sa.Column("canvas_data_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("video_projects", "canvas_data_json")

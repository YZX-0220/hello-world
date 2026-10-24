"""Persist immutable model-bound generation review.

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
"""

import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "video_project_versions", sa.Column("generation_review_json", sa.Text(), nullable=True)
    )


def downgrade():
    op.drop_column("video_project_versions", "generation_review_json")

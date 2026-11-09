"""Preserve image inputs and edit ancestry. Existing jobs used watermark=True."""

import sqlalchemy as sa
from alembic import op

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("image_jobs", sa.Column("parent_job_id", sa.String(64), nullable=True))
    op.add_column(
        "image_jobs",
        sa.Column("reference_images_json", sa.String(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "image_jobs",
        sa.Column("edit_context_json", sa.String(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "image_jobs", sa.Column("compiled_prompt", sa.String(), nullable=False, server_default="")
    )
    op.add_column(
        "image_jobs", sa.Column("watermark", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.create_index("ix_image_jobs_parent_job_id", "image_jobs", ["parent_job_id"])


def downgrade():
    op.drop_index("ix_image_jobs_parent_job_id", table_name="image_jobs")
    for name in (
        "watermark",
        "compiled_prompt",
        "edit_context_json",
        "reference_images_json",
        "parent_job_id",
    ):
        op.drop_column("image_jobs", name)

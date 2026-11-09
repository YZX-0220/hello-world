"""Persist image configurations and immutable generation tasks.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
"""

import sqlalchemy as sa
from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "image_api_configs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("display_name", sa.String(40), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("encrypted_api_key", sa.String(), nullable=False),
        sa.Column("key_hint", sa.String(12), nullable=False),
        sa.Column("account_label", sa.String(80), nullable=False),
        sa.Column("linked_video_api_config_id", sa.String(64)),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_image_api_configs_user_id", "image_api_configs", ["user_id"])
    op.create_table(
        "image_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "conversation_id",
            sa.String(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("api_config_id", sa.String(64), nullable=False),
        sa.Column("config_revision", sa.Integer(), nullable=False),
        sa.Column("channel_label", sa.String(80), nullable=False),
        sa.Column("account_label", sa.String(80), nullable=False),
        sa.Column("linked_video_api_config_id", sa.String(64)),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("prompt", sa.String(), nullable=False),
        sa.Column("aspect_ratio", sa.String(10), nullable=False),
        sa.Column("size", sa.String(30), nullable=False),
        sa.Column("source_node_id", sa.String(128)),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("encrypted_api_key", sa.String(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("simulation", sa.Boolean(), nullable=False),
        sa.Column("asset_id", sa.String(), sa.ForeignKey("assets.id", ondelete="SET NULL")),
        sa.Column("encrypted_result_url", sa.String()),
        sa.Column("provider_request_id", sa.String(200)),
        sa.Column("error_message", sa.String()),
        sa.Column("generated_at", sa.DateTime()),
        sa.Column("lease_until", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_image_job_request"),
    )
    for field in ("user_id", "conversation_id", "status", "lease_until"):
        op.create_index(f"ix_image_jobs_{field}", "image_jobs", [field])


def downgrade():
    op.drop_table("image_jobs")
    op.drop_table("image_api_configs")

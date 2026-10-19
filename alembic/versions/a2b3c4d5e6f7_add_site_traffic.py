"""Add anonymous visit tracking without touching existing user/project data.

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
"""

import sqlalchemy as sa
from alembic import op

revision = "a2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "site_visits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visitor_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("entry_path", sa.String(64), nullable=False),
        sa.Column("ip_hash", sa.String(64)),
        sa.Column("device_type", sa.String(20), nullable=False),
        sa.Column("browser", sa.String(40), nullable=False),
        sa.Column("operating_system", sa.String(40), nullable=False),
        sa.Column("referrer_host", sa.String(253)),
    )
    op.create_index("ix_site_visits_visitor_seen", "site_visits", ["visitor_hash", "last_seen_at"])
    op.create_table(
        "site_visit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visitor_hash", sa.String(64), nullable=False),
        sa.Column(
            "visit_id",
            sa.String(36),
            sa.ForeignKey("site_visits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_site_visit_events_created_at", "site_visit_events", ["created_at"])
    op.create_table(
        "site_traffic_totals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("total_visits", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_site_traffic_singleton"),
        sa.CheckConstraint("total_visits >= 0", name="ck_site_traffic_nonnegative"),
    )


def downgrade():
    op.drop_table("site_visit_events")
    op.drop_table("site_visits")
    op.drop_table("site_traffic_totals")

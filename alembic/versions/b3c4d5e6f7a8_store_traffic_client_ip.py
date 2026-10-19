"""Preserve normalized visitor IPs for later country/region lookup.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
"""

import sqlalchemy as sa
from alembic import op

revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    # Nullable additions preserve existing visits/counters. IP hashes cannot be
    # backfilled into real IPs: historical rows deliberately remain NULL.
    for table in ("site_visits", "site_visit_events"):
        op.add_column(table, sa.Column("ip_address", sa.String(45), nullable=True))
        op.add_column(table, sa.Column("ip_version", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("ip_is_public", sa.Boolean(), nullable=True))
        op.add_column(table, sa.Column("ip_source", sa.String(24), nullable=True))
        op.create_index(f"ix_{table}_ip_address", table, ["ip_address"])


def downgrade():
    for table in ("site_visit_events", "site_visits"):
        op.drop_index(f"ix_{table}_ip_address", table_name=table)
        for column in ("ip_source", "ip_is_public", "ip_version", "ip_address"):
            op.drop_column(table, column)

"""add storage_provider to assets table

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-10-26 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    # 增加 storage_provider 字段，历史存量数据默认为 'local'
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "storage_provider",
                sa.String(length=20),
                nullable=False,
                server_default="local",
            )
        )


def downgrade():
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.drop_column("storage_provider")

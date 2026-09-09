"""make video_jobs api_config_revision_id nullable

Revision ID: edad6462d9d0
Revises: 650c3368386f
Create Date: 2026-09-09 12:29:02.886457

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'edad6462d9d0'
down_revision = '650c3368386f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite 不支持 ALTER COLUMN DROP NOT NULL，用 batch（重建表）实现
    with op.batch_alter_table('video_jobs') as batch:
        batch.alter_column('api_config_revision_id', existing_type=sa.VARCHAR(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('video_jobs') as batch:
        batch.alter_column('api_config_revision_id', existing_type=sa.VARCHAR(), nullable=False)

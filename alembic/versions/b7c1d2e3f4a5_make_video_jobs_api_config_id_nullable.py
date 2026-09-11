"""make video_jobs api_config_id nullable

平台自有通道不引用用户视频配置，任务行 api_config_id 存 NULL（外键允许），
与 api_config_revision_id 对称；用户自配通道仍存真实 config.id。

Revision ID: b7c1d2e3f4a5
Revises: 8f2a1c4b6d5e
Create Date: 2026-09-10

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7c1d2e3f4a5"
down_revision = "8f2a1c4b6d5e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite 不支持 ALTER COLUMN DROP NOT NULL，用 batch（重建表）实现
    with op.batch_alter_table("video_jobs") as batch:
        batch.alter_column("api_config_id", existing_type=sa.VARCHAR(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("video_jobs") as batch:
        batch.alter_column("api_config_id", existing_type=sa.VARCHAR(), nullable=False)

"""add retrieval_notes to conversation_contexts

Revision ID: 8f2a1c4b6d5e
Revises: edad6462d9d0
Create Date: 2026-09-08 19:30:00.000000

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = '8f2a1c4b6d5e'
down_revision = 'edad6462d9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 新增列（SQLite 支持直接 ADD COLUMN）：联网搜索的详细依据累积，可空
    op.add_column('conversation_contexts', sa.Column('retrieval_notes', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('conversation_contexts', 'retrieval_notes')

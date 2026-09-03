"""Preserve original content for exact work-process synchronization.

Revision ID: 20260903_0006
Revises: 20260903_0005
"""
from alembic import op
import sqlalchemy as sa


revision = "20260903_0006"
down_revision = "20260903_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tasks", sa.Column("source_content", sa.Text(), nullable=True))
    op.execute(
        "UPDATE tasks SET source_content = content "
        "WHERE source_ref IS NOT NULL AND source_content IS NULL"
    )


def downgrade():
    op.drop_column("tasks", "source_content")

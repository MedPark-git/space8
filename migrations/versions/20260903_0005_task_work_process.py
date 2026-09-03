"""Add editable work process details to tasks.

Revision ID: 20260903_0005
Revises: 20260903_0004
"""
from alembic import op
import sqlalchemy as sa


revision = "20260903_0005"
down_revision = "20260903_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tasks", sa.Column("work_process", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("tasks", "work_process")

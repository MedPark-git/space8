"""Add selected task items for daily work journals.

Revision ID: 20260902_0003
Revises: 20260902_0002
"""
from alembic import op
import sqlalchemy as sa


revision = "20260902_0003"
down_revision = "20260902_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "work_journal_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("added_by_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("task_id", "work_date", "employee_id", name="uq_work_journal_item"),
    )
    op.create_index("ix_work_journal_items_task_id", "work_journal_items", ["task_id"])
    op.create_index("ix_work_journal_items_work_date", "work_journal_items", ["work_date"])
    op.create_index("ix_work_journal_items_employee_id", "work_journal_items", ["employee_id"])


def downgrade():
    op.drop_index("ix_work_journal_items_employee_id", table_name="work_journal_items")
    op.drop_index("ix_work_journal_items_work_date", table_name="work_journal_items")
    op.drop_index("ix_work_journal_items_task_id", table_name="work_journal_items")
    op.drop_table("work_journal_items")

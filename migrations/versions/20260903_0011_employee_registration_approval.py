"""Add administrator approval workflow for employee registrations.

Revision ID: 20260903_0011
Revises: 20260903_0010
"""
from alembic import op
import sqlalchemy as sa


revision = "20260903_0011"
down_revision = "20260903_0010"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(
            sa.Column(
                "approval_status",
                sa.String(length=20),
                nullable=False,
                server_default="승인완료",
            )
        )
        batch_op.add_column(sa.Column("approval_requested_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("approved_by_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_employees_approved_by_id_employees",
            "employees",
            ["approved_by_id"],
            ["id"],
        )
        batch_op.create_index("ix_employees_approval_status", ["approval_status"], unique=False)


def downgrade():
    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_index("ix_employees_approval_status")
        batch_op.drop_constraint("fk_employees_approved_by_id_employees", type_="foreignkey")
        batch_op.drop_column("approved_by_id")
        batch_op.drop_column("approved_at")
        batch_op.drop_column("approval_requested_at")
        batch_op.drop_column("approval_status")

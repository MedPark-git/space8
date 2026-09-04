"""Add participants and template fields to daily meetings.

Revision ID: 20260904_0014
Revises: 20260904_0013
"""
from alembic import op
import sqlalchemy as sa


revision = "20260904_0014"
down_revision = "20260904_0013"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("daily_meetings") as batch_op:
        batch_op.add_column(sa.Column("special_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("duration_minutes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("reporter_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("created_by_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_daily_meetings_reporter_id_employees",
            "employees",
            ["reporter_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_daily_meetings_created_by_id_employees",
            "employees",
            ["created_by_id"],
            ["id"],
        )

    op.create_table(
        "daily_meeting_attendees",
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["daily_meetings.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("meeting_id", "employee_id"),
    )

    op.execute(
        sa.text(
            "UPDATE daily_meetings "
            "SET reporter_id = author_id, created_by_id = author_id "
            "WHERE reporter_id IS NULL OR created_by_id IS NULL"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO daily_meeting_attendees (meeting_id, employee_id) "
            "SELECT id, author_id FROM daily_meetings"
        )
    )


def downgrade():
    op.drop_table("daily_meeting_attendees")
    with op.batch_alter_table("daily_meetings") as batch_op:
        batch_op.drop_constraint(
            "fk_daily_meetings_created_by_id_employees", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_daily_meetings_reporter_id_employees", type_="foreignkey"
        )
        batch_op.drop_column("created_by_id")
        batch_op.drop_column("reporter_id")
        batch_op.drop_column("duration_minutes")
        batch_op.drop_column("special_notes")

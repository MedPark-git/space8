"""Add saved major work and daily work journal documents.

Revision ID: 20260904_0015
Revises: 20260904_0014
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "20260904_0015"
down_revision = "20260904_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "work_journal_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("document_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("work_summary", sa.Text(), nullable=True),
        sa.Column("next_plan", sa.Text(), nullable=True),
        sa.Column("special_notes", sa.Text(), nullable=True),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "work_date",
            "document_type",
            "author_id",
            name="uq_work_journal_document_date_type_author",
        ),
    )
    op.create_index(
        op.f("ix_work_journal_documents_work_date"),
        "work_journal_documents",
        ["work_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_work_journal_documents_document_type"),
        "work_journal_documents",
        ["document_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_work_journal_documents_author_id"),
        "work_journal_documents",
        ["author_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_work_journal_documents_department_id"),
        "work_journal_documents",
        ["department_id"],
        unique=False,
    )
    op.create_table(
        "work_journal_document_items",
        sa.Column("journal_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["journal_id"],
            ["work_journal_documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("journal_id", "task_id"),
    )

    bind = op.get_bind()
    employees = sa.table(
        "employees",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("department_id", sa.Integer()),
    )
    legacy_items = sa.table(
        "work_journal_items",
        sa.column("task_id", sa.Integer()),
        sa.column("work_date", sa.Date()),
        sa.column("employee_id", sa.Integer()),
    )
    daily_logs = sa.table(
        "task_daily_logs",
        sa.column("task_id", sa.Integer()),
        sa.column("work_date", sa.Date()),
        sa.column("author_id", sa.Integer()),
    )
    documents = sa.table(
        "work_journal_documents",
        sa.column("id", sa.Integer()),
        sa.column("work_date", sa.Date()),
        sa.column("document_type", sa.String()),
        sa.column("title", sa.String()),
        sa.column("work_summary", sa.Text()),
        sa.column("next_plan", sa.Text()),
        sa.column("special_notes", sa.Text()),
        sa.column("author_id", sa.Integer()),
        sa.column("department_id", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    document_items = sa.table(
        "work_journal_document_items",
        sa.column("journal_id", sa.Integer()),
        sa.column("task_id", sa.Integer()),
    )

    employee_rows = bind.execute(
        sa.select(employees.c.id, employees.c.name, employees.c.department_id)
    ).all()
    employee_by_id = {
        row.id: {"name": row.name, "department_id": row.department_id}
        for row in employee_rows
    }
    legacy_pairs = {}
    for row in bind.execute(
        sa.select(
            legacy_items.c.work_date,
            legacy_items.c.employee_id,
            legacy_items.c.task_id,
        )
    ):
        legacy_pairs.setdefault((row.work_date, row.employee_id), set()).add(row.task_id)
    for row in bind.execute(
        sa.select(
            daily_logs.c.work_date,
            daily_logs.c.author_id,
            daily_logs.c.task_id,
        )
    ):
        legacy_pairs.setdefault((row.work_date, row.author_id), set()).add(row.task_id)

    timestamp = datetime.now(timezone.utc)
    for (work_date, employee_id), task_ids in sorted(
        legacy_pairs.items(),
        key=lambda item: (item[0][0], item[0][1]),
    ):
        employee = employee_by_id.get(employee_id)
        if not employee:
            continue
        bind.execute(
            documents.insert().values(
                work_date=work_date,
                document_type="daily",
                title=f"{work_date.isoformat()} {employee['name']} 일일업무 일지",
                work_summary=None,
                next_plan=None,
                special_notes=None,
                author_id=employee_id,
                department_id=employee["department_id"],
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        journal_id = bind.execute(
            sa.select(documents.c.id).where(
                documents.c.work_date == work_date,
                documents.c.document_type == "daily",
                documents.c.author_id == employee_id,
            )
        ).scalar_one()
        if task_ids:
            bind.execute(
                document_items.insert(),
                [
                    {"journal_id": journal_id, "task_id": task_id}
                    for task_id in sorted(task_ids)
                ],
            )


def downgrade():
    op.drop_table("work_journal_document_items")
    op.drop_index(
        op.f("ix_work_journal_documents_department_id"),
        table_name="work_journal_documents",
    )
    op.drop_index(
        op.f("ix_work_journal_documents_author_id"),
        table_name="work_journal_documents",
    )
    op.drop_index(
        op.f("ix_work_journal_documents_document_type"),
        table_name="work_journal_documents",
    )
    op.drop_index(
        op.f("ix_work_journal_documents_work_date"),
        table_name="work_journal_documents",
    )
    op.drop_table("work_journal_documents")

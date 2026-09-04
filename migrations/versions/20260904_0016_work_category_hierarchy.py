"""Add department work category hierarchy.

Revision ID: 20260904_0016
Revises: 20260904_0015
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "20260904_0016"
down_revision = "20260904_0015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "work_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("middle_name", sa.String(length=100), nullable=False),
        sa.Column("small_name", sa.String(length=150), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "department_id",
            "middle_name",
            "small_name",
            name="uq_work_category_path",
        ),
    )
    op.create_index(
        op.f("ix_work_categories_department_id"),
        "work_categories",
        ["department_id"],
        unique=False,
    )
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("work_category_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_tasks_work_category_id_work_categories",
            "work_categories",
            ["work_category_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_tasks_work_category_id",
            ["work_category_id"],
            unique=False,
        )

    bind = op.get_bind()
    tasks = sa.table(
        "tasks",
        sa.column("id", sa.Integer()),
        sa.column("department_id", sa.Integer()),
        sa.column("work_category_id", sa.Integer()),
        sa.column("source_category", sa.String()),
        sa.column("source_detail", sa.String()),
    )
    categories = sa.table(
        "work_categories",
        sa.column("id", sa.Integer()),
        sa.column("department_id", sa.Integer()),
        sa.column("middle_name", sa.String()),
        sa.column("small_name", sa.String()),
        sa.column("active", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    task_rows = bind.execute(
        sa.select(
            tasks.c.id,
            tasks.c.department_id,
            tasks.c.source_category,
            tasks.c.source_detail,
        ).where(tasks.c.source_category.is_not(None))
    ).all()
    category_ids = {}
    timestamp = datetime.now(timezone.utc)
    for row in task_rows:
        middle_name = (row.source_category or "").strip()
        small_name = (row.source_detail or "").strip()
        if not middle_name:
            continue
        key = (row.department_id, middle_name, small_name)
        category_id = category_ids.get(key)
        if category_id is None:
            category_id = bind.execute(
                sa.select(categories.c.id).where(
                    categories.c.department_id == row.department_id,
                    categories.c.middle_name == middle_name,
                    categories.c.small_name == small_name,
                )
            ).scalar_one_or_none()
            if category_id is None:
                bind.execute(
                    categories.insert().values(
                        department_id=row.department_id,
                        middle_name=middle_name,
                        small_name=small_name,
                        active=True,
                        sort_order=0,
                        created_at=timestamp,
                    )
                )
                category_id = bind.execute(
                    sa.select(categories.c.id).where(
                        categories.c.department_id == row.department_id,
                        categories.c.middle_name == middle_name,
                        categories.c.small_name == small_name,
                    )
                ).scalar_one()
            category_ids[key] = category_id
        bind.execute(
            tasks.update()
            .where(tasks.c.id == row.id)
            .values(work_category_id=category_id)
        )


def downgrade():
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_index("ix_tasks_work_category_id")
        batch_op.drop_constraint(
            "fk_tasks_work_category_id_work_categories",
            type_="foreignkey",
        )
        batch_op.drop_column("work_category_id")
    op.drop_index(
        op.f("ix_work_categories_department_id"),
        table_name="work_categories",
    )
    op.drop_table("work_categories")

import os
import unittest
from datetime import date, datetime, timedelta, timezone

from werkzeug.security import generate_password_hash


os.environ.setdefault("ALLOW_IN_MEMORY_DB", "1")
os.environ.setdefault("SESSION_COOKIE_SECURE", "0")
os.environ.setdefault(
    "BOOTSTRAP_ADMIN_PASSWORD_HASH",
    generate_password_hash("StartupAdmin123", method="scrypt"),
)

from app import (  # noqa: E402
    AuditLog,
    Department,
    Employee,
    Role,
    Task,
    TaskClassification,
    advance_recurrence_date,
    create_app,
    db,
    generate_due_recurring_tasks,
)


class TaskRecurrenceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "WTF_CSRF_ENABLED": False,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        self.department = Department(name="보안전산팀", active=True)
        self.role = Role(
            name="관리자",
            data_scope="all",
            permissions={"task_manage_all": True},
            is_system=True,
        )
        db.session.add_all([self.department, self.role])
        db.session.flush()
        self.admin = Employee(
            name="관리자",
            department=self.department,
            position="관리자",
            login_id="admin1",
            password_hash="",
            status="재직",
            approval_status="승인완료",
            role=self.role,
            must_change_password=False,
        )
        self.admin.set_password("AdminPass123")
        db.session.add(self.admin)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def create_root(self, title, repeat_cycle, start_date, target_date=None, **overrides):
        values = {
            "title": title,
            "content": "반복 업무 내용",
            "work_process": "1. 확인\n2. 처리",
            "department_id": self.department.id,
            "assignee_id": self.admin.id,
            "start_date": start_date,
            "target_date": target_date or start_date,
            "status": "완료",
            "progress": 100,
            "repeat_cycle": repeat_cycle,
            "repeat_detail": "정기 업무",
            "created_by_id": self.admin.id,
        }
        values.update(overrides)
        task = Task(**values)
        task.classifications.append(TaskClassification(name="루틴"))
        db.session.add(task)
        db.session.flush()
        return task

    def test_requested_cycles_generate_due_occurrence_once(self):
        roots = {
            "주간": self.create_root("주간 점검", "주간", date(2026, 8, 28), date(2026, 8, 30)),
            "월간": self.create_root("월간 점검", "월간", date(2026, 8, 4), date(2026, 8, 6)),
            "분기": self.create_root("분기 점검", "분기", date(2026, 6, 4), date(2026, 6, 6)),
            "반기": self.create_root("반기 점검", "반기", date(2026, 3, 4), date(2026, 3, 6)),
            "연간": self.create_root("연간 점검", "연간", date(2025, 9, 4), date(2025, 9, 6)),
        }
        db.session.commit()

        created_ids = generate_due_recurring_tasks(date(2026, 9, 4))
        self.assertEqual(len(created_ids), 5)
        occurrences = db.session.scalars(
            db.select(Task).where(Task.recurrence_root_id.is_not(None)).order_by(Task.id)
        ).all()
        self.assertEqual(len(occurrences), 5)
        for occurrence in occurrences:
            self.assertEqual(occurrence.start_date, date(2026, 9, 4))
            self.assertEqual(occurrence.target_date, date(2026, 9, 6))
            self.assertEqual(occurrence.status, "진행중")
            self.assertEqual(occurrence.progress, 0)
            self.assertEqual(occurrence.recurrence_sequence, 1)
            self.assertEqual(occurrence.type_names, ["루틴"])
            self.assertIn(occurrence.recurrence_root_id, {root.id for root in roots.values()})

        self.assertEqual(generate_due_recurring_tasks(date(2026, 9, 4)), [])
        self.assertEqual(
            db.session.scalar(
                db.select(db.func.count(Task.id)).where(Task.recurrence_root_id.is_not(None))
            ),
            5,
        )
        self.assertEqual(
            db.session.scalar(
                db.select(db.func.count(AuditLog.id)).where(
                    AuditLog.action == "TASK_RECURRENCE_CREATE"
                )
            ),
            5,
        )

    def test_month_end_and_leap_year_dates_do_not_drift(self):
        self.assertEqual(
            advance_recurrence_date(date(2026, 1, 31), "월간", 1),
            date(2026, 2, 28),
        )
        self.assertEqual(
            advance_recurrence_date(date(2026, 1, 31), "월간", 2),
            date(2026, 3, 31),
        )
        self.assertEqual(
            advance_recurrence_date(date(2028, 2, 29), "연간", 1),
            date(2029, 2, 28),
        )

    def test_missed_monthly_occurrences_are_caught_up(self):
        root = self.create_root("월말 정산", "월간", date(2026, 1, 31))
        db.session.commit()

        created_ids = generate_due_recurring_tasks(date(2026, 3, 31))
        self.assertEqual(len(created_ids), 2)
        occurrences = db.session.scalars(
            db.select(Task)
            .where(Task.recurrence_root_id == root.id)
            .order_by(Task.recurrence_sequence)
        ).all()
        self.assertEqual(
            [(item.recurrence_sequence, item.start_date) for item in occurrences],
            [(1, date(2026, 2, 28)), (2, date(2026, 3, 31))],
        )

    def test_future_or_deleted_series_does_not_generate(self):
        self.create_root("미도래 주간", "주간", date(2026, 9, 1))
        deleted = self.create_root("삭제된 주간", "주간", date(2026, 8, 28))
        deleted.deleted_at = datetime.now(timezone.utc)
        db.session.commit()

        self.assertEqual(generate_due_recurring_tasks(date(2026, 9, 4)), [])

    def test_generated_task_inherits_operational_fields_without_duplication_source_ref(self):
        root = self.create_root(
            "원본 주간 점검",
            "주간",
            date(2026, 8, 28),
            calendar_selected=True,
            calendar_registered_by_id=self.admin.id,
            source_ref="security-it:weekly-check",
            source_name="경영_보안전산팀 업무분장_260902.xlsx",
            source_category="보안",
            source_detail="주간 점검",
            source_content="반복 업무 내용",
            source_assignees="관리자",
            source_frequency="주1회",
        )
        db.session.commit()

        [created_id] = generate_due_recurring_tasks(date(2026, 9, 4))
        occurrence = db.session.get(Task, created_id)
        self.assertEqual(occurrence.recurrence_root_id, root.id)
        self.assertEqual(occurrence.content, root.content)
        self.assertEqual(occurrence.work_process, root.work_process)
        self.assertTrue(occurrence.calendar_selected)
        self.assertTrue(occurrence.calendar_included)
        self.assertIsNone(occurrence.source_ref)
        self.assertEqual(occurrence.source_name, root.source_name)
        self.assertTrue(occurrence.is_source_import)
        self.assertEqual(
            db.session.scalar(
                db.select(db.func.count(Task.id)).where(
                    Task.source_name == root.source_name,
                    Task.recurrence_root_id.is_(None),
                )
            ),
            1,
        )

    def test_task_form_explains_automatic_recurrence(self):
        client = self.app.test_client()
        client.post("/login", data={"login_id": "admin1", "password": "AdminPass123"})

        page = client.get("/tasks/new")
        self.assertEqual(page.status_code, 200)
        for label in ("매주 1회", "매월 1회", "분기 1회", "반기 1회", "매년 1회"):
            self.assertIn(label.encode(), page.data)
        self.assertIn("다음 주기 시작일에 새 업무로 자동 생성".encode(), page.data)


if __name__ == "__main__":
    unittest.main()

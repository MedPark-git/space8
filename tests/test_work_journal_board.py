import os
import importlib
import unittest
from datetime import date
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
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
    TaskDailyLog,
    WorkJournalDocument,
    WorkJournalItem,
    create_app,
    db,
)


class WorkJournalBoardTests(unittest.TestCase):
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

        self.security = Department(name="보안전산팀", active=True)
        self.finance = Department(name="재무운영팀", active=True)
        self.roles = {
            "관리자": Role(
                name="관리자",
                data_scope="all",
                permissions={"task_manage_all": True},
                is_system=True,
            ),
            "부서장": Role(
                name="부서장",
                data_scope="all",
                permissions={"task_manage_department": True},
                is_system=True,
            ),
            "팀장": Role(
                name="팀장",
                data_scope="all",
                permissions={"task_manage_department": True},
                is_system=True,
            ),
            "팀원": Role(
                name="팀원",
                data_scope="department",
                permissions={"task_manage_department": True},
                is_system=True,
            ),
        }
        db.session.add_all([self.security, self.finance, *self.roles.values()])
        db.session.flush()

        self.users = {}
        for login_id, name, department, role_name in (
            ("author1", "보안 작성자", self.security, "팀원"),
            ("peer1", "보안 동료", self.security, "팀원"),
            ("lead1", "보안 팀장", self.security, "팀장"),
            ("financelead", "재무 팀장", self.finance, "팀장"),
            ("head1", "경영 부서장", self.finance, "부서장"),
            ("admin1", "시스템 관리자", self.finance, "관리자"),
        ):
            employee = Employee(
                name=name,
                department=department,
                position=role_name,
                login_id=login_id,
                password_hash="",
                status="재직",
                approval_status="승인완료",
                role=self.roles[role_name],
                must_change_password=False,
            )
            employee.set_password("UserPass123")
            db.session.add(employee)
            self.users[login_id] = employee
        db.session.flush()

        self.major_task = self.create_task("정보보안 개선", "주요")
        self.general_task = self.create_task("금일 장비 점검", "일반")
        self.daily_log = TaskDailyLog(
            task=self.general_task,
            work_date=date(2026, 9, 4),
            content="장비 12대 점검 완료",
            author=self.users["author1"],
        )
        db.session.add(self.daily_log)
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def create_task(self, title, classification):
        task = Task(
            title=title,
            content=f"{title} 상세",
            department=self.security,
            assignee=self.users["author1"],
            start_date=date(2026, 9, 1),
            target_date=date(2026, 9, 30),
            status="진행중",
            progress=30,
            repeat_cycle="없음",
            creator=self.users["author1"],
        )
        task.classifications.append(TaskClassification(name=classification))
        db.session.add(task)
        db.session.flush()
        return task

    def login(self, login_id):
        self.client.post("/logout")
        response = self.client.post(
            "/login",
            data={"login_id": login_id, "password": "UserPass123"},
        )
        self.assertEqual(response.status_code, 302)

    def create_daily_document(self):
        journal = WorkJournalDocument(
            work_date=date(2026, 9, 4),
            document_type="daily",
            title="보안팀 일일업무 일지",
            work_summary="금일 보안 장비 점검",
            next_plan="익일 계정 점검",
            author=self.users["author1"],
            department=self.security,
            tasks=[self.general_task],
        )
        db.session.add(journal)
        db.session.commit()
        return journal

    def test_board_offers_two_document_types_and_popup_view(self):
        self.login("author1")
        response = self.client.get("/journals")
        self.assertEqual(response.status_code, 200)
        self.assertIn("업무일지 게시판".encode(), response.data)
        self.assertIn(b'data-journal-compose="major"', response.data)
        self.assertIn(b'data-journal-compose="daily"', response.data)
        self.assertIn('value="major"'.encode(), response.data)
        self.assertIn('value="daily"'.encode(), response.data)
        self.assertIn("본인 · 같은 부서(팀)의 팀장 · 부서장".encode(), response.data)
        self.assertIn(self.major_task.title.encode(), response.data)
        self.assertIn(self.general_task.title.encode(), response.data)

    def test_daily_document_is_saved_and_opened_from_board_dialog(self):
        self.login("author1")
        response = self.client.post(
            "/journals",
            data={
                "document_type": "daily",
                "work_date": "2026-09-04",
                "title": "보안팀 일일업무 일지",
                "task_ids": [str(self.general_task.id)],
                "work_summary": "장비 점검 완료",
                "next_plan": "계정 권한 점검",
                "special_notes": "이상 없음",
            },
        )
        self.assertEqual(response.status_code, 302)
        journal = db.session.scalar(db.select(WorkJournalDocument))
        self.assertEqual(journal.document_type, "daily")
        self.assertEqual(journal.tasks, [self.general_task])
        self.assertEqual(response.headers["Location"], f"/journals?open={journal.id}")

        board = self.client.get(response.headers["Location"])
        self.assertIn(f'data-auto-preview="/journals/{journal.id}/preview"'.encode(), board.data)
        self.assertIn(f'data-journal-preview="/journals/{journal.id}/preview"'.encode(), board.data)
        preview = self.client.get(f"/journals/{journal.id}/preview")
        self.assertIn("장비 점검 완료".encode(), preview.data)
        self.assertIn("장비 12대 점검 완료".encode(), preview.data)
        self.assertIn(b"data-print-journal", preview.data)
        self.assertIn(b"data-download-image", preview.data)
        self.assertIn("A4 인쇄".encode(), preview.data)
        self.assertIn("PNG 이미지 저장".encode(), preview.data)
        audit = db.session.scalar(
            db.select(AuditLog).where(AuditLog.action == "WORK_JOURNAL_DOCUMENT_CREATE")
        )
        self.assertIsNotNone(audit)

    def test_major_document_rejects_non_major_task(self):
        self.login("author1")
        response = self.client.post(
            "/journals",
            data={
                "document_type": "major",
                "work_date": "2026-09-04",
                "task_ids": [str(self.general_task.id)],
                "work_summary": "주요 업무 요약",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            db.session.scalar(db.select(db.func.count(WorkJournalDocument.id))),
            0,
        )

    def test_daily_journal_visibility_is_limited_to_author_team_leader_and_head(self):
        journal = self.create_daily_document()
        access_expectations = {
            "author1": 200,
            "peer1": 403,
            "lead1": 200,
            "financelead": 403,
            "head1": 200,
            "admin1": 403,
        }
        for login_id, expected_status in access_expectations.items():
            with self.subTest(login_id=login_id):
                self.login(login_id)
                preview = self.client.get(f"/journals/{journal.id}/preview")
                self.assertEqual(preview.status_code, expected_status)
                board = self.client.get("/journals")
                if expected_status == 200:
                    self.assertIn(journal.title.encode(), board.data)
                else:
                    self.assertNotIn(journal.title.encode(), board.data)

    def test_only_author_can_edit_daily_journal(self):
        journal = self.create_daily_document()
        self.login("lead1")
        self.assertEqual(self.client.get(f"/journals/{journal.id}/edit").status_code, 403)
        self.login("head1")
        self.assertEqual(self.client.get(f"/journals/{journal.id}/edit").status_code, 403)
        self.login("author1")
        self.assertEqual(self.client.get(f"/journals/{journal.id}/edit").status_code, 200)

    def test_task_daily_logs_use_the_same_private_visibility_rule(self):
        access_expectations = {
            "author1": True,
            "peer1": False,
            "lead1": True,
            "financelead": False,
            "head1": True,
            "admin1": False,
        }
        for login_id, can_see in access_expectations.items():
            with self.subTest(login_id=login_id):
                self.login(login_id)
                response = self.client.get(f"/tasks/{self.general_task.id}")
                self.assertEqual(response.status_code, 200)
                if can_see:
                    self.assertIn(self.daily_log.content.encode(), response.data)
                else:
                    self.assertNotIn(self.daily_log.content.encode(), response.data)

    def test_existing_journal_items_can_default_into_daily_document(self):
        db.session.add(
            WorkJournalItem(
                task=self.general_task,
                work_date=date.today(),
                employee=self.users["author1"],
                added_by=self.users["lead1"],
            )
        )
        db.session.commit()
        self.login("author1")
        response = self.client.get("/journals")
        self.assertIn(
            f'name="task_ids" value="{self.general_task.id}" checked'.encode(),
            response.data,
        )

    def test_journal_print_styles_use_a4_portrait_and_local_png_export(self):
        stylesheet = Path(self.app.root_path, "static", "style.css").read_text(encoding="utf-8")
        script = Path(self.app.root_path, "static", "app.js").read_text(encoding="utf-8")
        self.assertIn("@page{size:A4 portrait;margin:12mm}", stylesheet)
        self.assertIn(".journal-document{width:186mm!important", stylesheet)
        self.assertIn('[data-print-meeting], [data-print-journal]', script)
        self.assertIn("initJournalBoard", script)
        self.assertIn("downloadElementAsPng", script)

    def test_migration_backfills_legacy_items_and_logs_into_saved_daily_document(self):
        engine = sa.create_engine("sqlite://")
        metadata = sa.MetaData()
        departments = sa.Table(
            "departments",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String),
        )
        employees = sa.Table(
            "employees",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String),
            sa.Column("department_id", sa.Integer),
        )
        tasks = sa.Table(
            "tasks",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
        )
        legacy_items = sa.Table(
            "work_journal_items",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("task_id", sa.Integer),
            sa.Column("work_date", sa.Date),
            sa.Column("employee_id", sa.Integer),
        )
        daily_logs = sa.Table(
            "task_daily_logs",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("task_id", sa.Integer),
            sa.Column("work_date", sa.Date),
            sa.Column("author_id", sa.Integer),
        )
        metadata.create_all(engine)

        with engine.begin() as connection:
            connection.execute(departments.insert(), {"id": 1, "name": "보안전산팀"})
            connection.execute(
                employees.insert(),
                {"id": 1, "name": "기존 작성자", "department_id": 1},
            )
            connection.execute(tasks.insert(), [{"id": 1}, {"id": 2}])
            connection.execute(
                legacy_items.insert(),
                {
                    "id": 1,
                    "task_id": 1,
                    "work_date": date(2026, 9, 3),
                    "employee_id": 1,
                },
            )
            connection.execute(
                daily_logs.insert(),
                [
                    {
                        "id": 1,
                        "task_id": 1,
                        "work_date": date(2026, 9, 3),
                        "author_id": 1,
                    },
                    {
                        "id": 2,
                        "task_id": 2,
                        "work_date": date(2026, 9, 3),
                        "author_id": 1,
                    },
                ],
            )

            migration = importlib.import_module(
                "migrations.versions.20260904_0015_work_journal_documents"
            )
            original_op = migration.op
            migration.op = Operations(MigrationContext.configure(connection))
            try:
                migration.upgrade()
            finally:
                migration.op = original_op

            document = connection.execute(
                sa.text(
                    "SELECT id, document_type, title, author_id, department_id "
                    "FROM work_journal_documents"
                )
            ).mappings().one()
            linked_tasks = connection.execute(
                sa.text(
                    "SELECT task_id FROM work_journal_document_items "
                    "WHERE journal_id = :journal_id ORDER BY task_id"
                ),
                {"journal_id": document["id"]},
            ).scalars().all()

        self.assertEqual(document["document_type"], "daily")
        self.assertIn("기존 작성자 일일업무 일지", document["title"])
        self.assertEqual(document["author_id"], 1)
        self.assertEqual(document["department_id"], 1)
        self.assertEqual(linked_tasks, [1, 2])


if __name__ == "__main__":
    unittest.main()

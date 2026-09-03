import os
import unittest
from datetime import date

from werkzeug.security import generate_password_hash


os.environ.setdefault("ALLOW_IN_MEMORY_DB", "1")
os.environ.setdefault("SESSION_COOKIE_SECURE", "0")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD_HASH", generate_password_hash("StartupAdmin123", method="scrypt"))

from app import (  # noqa: E402
    Department,
    Employee,
    Role,
    Task,
    TaskClassification,
    create_app,
    db,
)


class TaskWorkProcessTests(unittest.TestCase):
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

        department = Department(name="보안전산팀", active=True)
        role = Role(name="관리자", data_scope="all", permissions={}, is_system=True)
        db.session.add_all([department, role])
        db.session.flush()
        self.admin = Employee(
            name="관리자",
            department=department,
            position="팀장",
            login_id="admin1",
            password_hash="",
            status="재직",
            role=role,
            must_change_password=False,
        )
        self.admin.set_password("AdminPass123")
        db.session.add(self.admin)
        db.session.flush()
        self.task = Task(
            title="DRM · 모니터링",
            content="감사 이력내역 확인",
            department=department,
            assignee=self.admin,
            start_date=date(2026, 9, 2),
            target_date=date(2026, 9, 2),
            status="진행중",
            progress=0,
            repeat_cycle="일간",
            repeat_detail="일",
            source_ref="security-it:drm-monitoring",
            source_name="경영_보안전산팀 업무분장_260902.xlsx",
            source_category="DRM",
            source_detail="모니터링",
            source_assignees="권민기, 김영재",
            source_frequency="일",
            creator=self.admin,
        )
        self.task.classifications.append(TaskClassification(name="루틴"))
        db.session.add(self.task)
        db.session.commit()
        self.task_id = self.task.id
        self.department_id = department.id
        self.admin_id = self.admin.id
        self.client = self.app.test_client()
        self.client.post("/login", data={"login_id": "admin1", "password": "AdminPass123"})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def task_payload(self, work_process):
        return {
            "task_types": ["루틴"],
            "title": "DRM · 모니터링",
            "content": "감사 이력내역 확인",
            "work_process": work_process,
            "department_id": self.department_id,
            "assignee_id": self.admin_id,
            "start_date": "2026-09-02",
            "target_date": "2026-09-02",
            "status": "진행중",
            "progress": "0",
            "repeat_cycle": "일간",
            "repeat_detail": "일",
        }

    def test_process_field_is_directly_after_task_content(self):
        response = self.client.get(f"/tasks/{self.task_id}/edit")
        self.assertEqual(response.status_code, 200)
        content_position = response.data.index(b'name="content"')
        process_position = response.data.index(b'name="work_process"')
        department_position = response.data.index(b'name="department_id"')
        self.assertLess(content_position, process_position)
        self.assertLess(process_position, department_position)

    def test_process_can_be_saved_updated_and_displayed_with_line_breaks(self):
        first_process = "1. DRM 접속\n2. 감사 이력 확인\n3. 이상 내역 기록"
        response = self.client.post(
            f"/tasks/{self.task_id}/edit",
            data=self.task_payload(first_process),
        )
        self.assertEqual(response.status_code, 302)
        task = db.session.get(Task, self.task_id)
        self.assertEqual(task.work_process, first_process)

        detail = self.client.get(f"/tasks/{self.task_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("업무 프로세스".encode(), detail.data)
        self.assertIn(first_process.encode(), detail.data)

        updated_process = "1. 전일 로그 확인\n2. 정책 위반 검토\n3. 담당자 보고"
        response = self.client.post(
            f"/tasks/{self.task_id}/edit",
            data=self.task_payload(updated_process),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(Task, self.task_id).work_process, updated_process)

    def test_empty_process_has_clear_detail_state(self):
        detail = self.client.get(f"/tasks/{self.task_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("등록된 업무 프로세스가 없습니다".encode(), detail.data)


if __name__ == "__main__":
    unittest.main()

import os
import unittest
from datetime import date

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
    create_app,
    db,
)


class TaskDeleteTests(unittest.TestCase):
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
        roles = {
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
        db.session.add_all([self.security, self.finance, *roles.values()])
        db.session.flush()

        self.users = {}
        for login_id, name, department, role_name in (
            ("admin1", "관리자", self.finance, "관리자"),
            ("head1", "보안 부서장", self.security, "부서장"),
            ("lead1", "보안 팀장", self.security, "팀장"),
            ("member1", "보안 팀원", self.security, "팀원"),
            ("financelead", "재무 팀장", self.finance, "팀장"),
        ):
            employee = Employee(
                name=name,
                department=department,
                position=role_name if role_name != "관리자" else "부서장",
                login_id=login_id,
                password_hash="",
                status="재직",
                role=roles[role_name],
                must_change_password=False,
            )
            employee.set_password("UserPass123")
            db.session.add(employee)
            self.users[login_id] = employee
        db.session.flush()

        self.security_task = self.create_task("보안 삭제 대상", self.security, self.users["member1"])
        self.finance_task = self.create_task("재무 삭제 대상", self.finance, self.users["financelead"])
        db.session.add(
            TaskDailyLog(
                task=self.security_task,
                work_date=date.today(),
                content="삭제 전 업무 기록",
                author=self.users["member1"],
            )
        )
        db.session.commit()
        self.security_task_id = self.security_task.id
        self.finance_task_id = self.finance_task.id
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def create_task(self, title, department, assignee):
        task = Task(
            title=title,
            content="업무 내용",
            department=department,
            assignee=assignee,
            start_date=date.today(),
            target_date=date.today(),
            status="진행중",
            progress=0,
            repeat_cycle="없음",
            creator=self.users["admin1"],
        )
        task.classifications.append(TaskClassification(name="일반"))
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

    def test_team_lead_can_soft_delete_own_department_task_and_history_is_preserved(self):
        self.login("lead1")
        page = self.client.get("/tasks")
        self.assertIn(f'/tasks/{self.security_task_id}/delete'.encode(), page.data)
        self.assertNotIn(f'/tasks/{self.finance_task_id}/delete'.encode(), page.data)

        response = self.client.post(
            f"/tasks/{self.security_task_id}/delete",
            data={"return_to": "/tasks"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        task = db.session.get(Task, self.security_task_id)
        self.assertIsNotNone(task)
        self.assertIsNotNone(task.deleted_at)
        self.assertEqual(task.deleted_by_id, self.users["lead1"].id)
        self.assertEqual(
            db.session.scalar(
                db.select(db.func.count(TaskDailyLog.id)).where(
                    TaskDailyLog.task_id == self.security_task_id
                )
            ),
            1,
        )
        self.assertNotIn("보안 삭제 대상".encode(), response.data)
        self.assertEqual(self.client.get(f"/tasks/{self.security_task_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/tasks/{self.security_task_id}/edit").status_code, 404)
        audit = db.session.scalar(
            db.select(AuditLog).where(
                AuditLog.action == "TASK_DELETE",
                AuditLog.target == f"task:{self.security_task_id}",
            )
        )
        self.assertIsNotNone(audit)
        self.assertTrue(audit.details["history_preserved"])

    def test_department_head_can_delete_own_department_task(self):
        self.login("head1")
        response = self.client.post(f"/tasks/{self.security_task_id}/delete")
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(db.session.get(Task, self.security_task_id).deleted_at)

    def test_admin_can_delete_another_department_task(self):
        self.login("admin1")
        response = self.client.post(f"/tasks/{self.security_task_id}/delete")
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(db.session.get(Task, self.security_task_id).deleted_at)

    def test_team_member_cannot_delete_even_with_department_manage_permission(self):
        self.login("member1")
        page = self.client.get("/tasks")
        self.assertNotIn(f'/tasks/{self.security_task_id}/delete'.encode(), page.data)
        response = self.client.post(f"/tasks/{self.security_task_id}/delete")
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(db.session.get(Task, self.security_task_id).deleted_at)

    def test_team_lead_cannot_delete_another_department_task(self):
        self.login("lead1")
        response = self.client.post(f"/tasks/{self.finance_task_id}/delete")
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(db.session.get(Task, self.finance_task_id).deleted_at)

    def test_delete_endpoint_rejects_get_requests(self):
        self.login("admin1")
        response = self.client.get(f"/tasks/{self.security_task_id}/delete")
        self.assertEqual(response.status_code, 405)


if __name__ == "__main__":
    unittest.main()

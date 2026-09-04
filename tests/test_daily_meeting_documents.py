import os
import io
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree
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
    DailyMeeting,
    Department,
    Employee,
    Role,
    Task,
    TaskClassification,
    create_app,
    db,
)


class DailyMeetingDocumentTests(unittest.TestCase):
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

        self.department = Department(name="인사총무팀", active=True)
        self.admin_role = Role(
            name="관리자",
            data_scope="all",
            permissions={"task_manage_all": True},
            is_system=True,
        )
        db.session.add_all([self.department, self.admin_role])
        db.session.flush()
        self.admin = Employee(
            name="관리자",
            department=self.department,
            position="부서장",
            login_id="admin1",
            password_hash="",
            status="재직",
            approval_status="승인완료",
            role=self.admin_role,
            must_change_password=False,
        )
        self.admin.set_password("AdminPass123")
        db.session.add(self.admin)
        db.session.flush()
        self.task = Task(
            title="채용 프로세스 정비",
            content="신규 채용 진행사항 점검",
            department=self.department,
            assignee=self.admin,
            start_date=date(2026, 9, 4),
            target_date=date(2026, 9, 11),
            status="진행중",
            progress=20,
            repeat_cycle="없음",
            creator=self.admin,
        )
        self.task.classifications.append(TaskClassification(name="주요"))
        db.session.add(self.task)
        db.session.commit()
        self.client = self.app.test_client()
        self.client.post("/login", data={"login_id": "admin1", "password": "AdminPass123"})

    def meeting_people(self):
        return {
            "author_id": str(self.admin.id),
            "reporter_id": str(self.admin.id),
            "attendee_ids": [str(self.admin.id)],
        }

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_list_offers_agenda_and_minutes_writing_modes(self):
        response = self.client.get("/meetings")
        self.assertEqual(response.status_code, 200)
        self.assertIn('value="agenda"'.encode(), response.data)
        self.assertIn('value="minutes"'.encode(), response.data)
        self.assertIn("일일 회의 아젠다".encode(), response.data)
        self.assertIn("일일 회의 회의록".encode(), response.data)

    def test_agenda_can_be_created_without_related_task(self):
        response = self.client.post(
            "/meetings",
            data={**self.meeting_people(),
                "document_type": "agenda",
                "meeting_date": "2026-09-04",
                "title": "경영사업본부 아침 회의 아젠다",
                "agenda_content": "1. 채용 진행현황\n2. 자금 집행계획",
            },
        )
        self.assertEqual(response.status_code, 302)
        meeting = db.session.scalar(db.select(DailyMeeting))
        self.assertEqual(meeting.document_type, "agenda")
        self.assertEqual(meeting.agenda_content, "1. 채용 진행현황\n2. 자금 집행계획")
        self.assertEqual(meeting.tasks, [])
        detail = self.client.get(response.headers["Location"])
        self.assertIn("아젠다 및 사전 공유사항".encode(), detail.data)
        self.assertIn(b"data-download-image", detail.data)
        self.assertIn(b"window.print()", detail.data)
        self.assertIn("Excel 양식 다운로드".encode(), detail.data)
        self.assertIn("A4 인쇄".encode(), detail.data)
        self.assertIn("PNG 이미지 저장".encode(), detail.data)

    def test_meeting_print_styles_use_a4_portrait(self):
        stylesheet = Path(self.app.root_path, "static", "style.css").read_text(encoding="utf-8")
        self.assertIn("@page{size:A4 portrait;margin:12mm}", stylesheet)
        self.assertIn("width:186mm!important", stylesheet)
        self.assertIn("print-color-adjust:exact", stylesheet)

    def test_minutes_can_be_created_with_written_sections_and_task(self):
        response = self.client.post(
            "/meetings",
            data={**self.meeting_people(),
                "document_type": "minutes",
                "meeting_date": "2026-09-04",
                "title": "9월 4일 일일 회의록",
                "discussion_notes": "채용 일정과 담당자를 논의함",
                "decisions": "공고를 금일까지 게시",
                "action_items": "김영재: 공고 검토 / 9월 4일",
                "task_ids": [str(self.task.id)],
            },
        )
        self.assertEqual(response.status_code, 302)
        meeting = db.session.scalar(db.select(DailyMeeting))
        self.assertEqual(meeting.document_type, "minutes")
        self.assertEqual(meeting.tasks, [self.task])
        self.assertEqual(meeting.author, self.admin)
        self.assertEqual(meeting.reporter, self.admin)
        self.assertEqual(meeting.attendees, [self.admin])
        detail = self.client.get(response.headers["Location"])
        self.assertIn("주요 논의사항".encode(), detail.data)
        self.assertIn("결정사항".encode(), detail.data)
        self.assertIn("후속 조치사항".encode(), detail.data)
        self.assertIn(self.task.title.encode(), detail.data)
        excel = self.client.get(f"/meetings/{meeting.id}/excel")
        self.assertEqual(excel.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(excel.data)) as workbook:
            sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
            self.assertIn("경영 일일회의_09/04(금)", sheet_xml)
            self.assertIn("채용 일정과 담당자를 논의함", sheet_xml)

    def test_document_can_be_edited_and_audited(self):
        meeting = DailyMeeting(
            meeting_date=date(2026, 9, 4),
            document_type="agenda",
            title="수정 전 아젠다",
            agenda_content="수정 전 내용",
            author=self.admin,
            department=self.department,
        )
        db.session.add(meeting)
        db.session.commit()

        response = self.client.post(
            f"/meetings/{meeting.id}/edit",
            data={**self.meeting_people(),
                "document_type": "minutes",
                "meeting_date": "2026-09-05",
                "title": "수정된 회의록",
                "discussion_notes": "수정된 논의내용",
                "decisions": "수정된 결정사항",
                "action_items": "후속 조치",
            },
        )
        self.assertEqual(response.status_code, 302)
        db.session.refresh(meeting)
        self.assertEqual(meeting.document_type, "minutes")
        self.assertIsNone(meeting.agenda_content)
        self.assertEqual(meeting.decisions, "수정된 결정사항")
        log = db.session.scalar(
            db.select(AuditLog).where(
                AuditLog.action == "MEETING_UPDATE",
                AuditLog.target == f"meeting:{meeting.id}",
            )
        )
        self.assertIsNotNone(log)

    def test_empty_document_is_not_created(self):
        response = self.client.post(
            "/meetings",
            data={
                **self.meeting_people(),
                "document_type": "agenda",
                "meeting_date": "2026-09-04",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(db.session.scalar(db.select(db.func.count(DailyMeeting.id))), 0)
        self.assertIn("회의 내용 또는 관련 업무".encode(), response.data)

    def test_all_visible_task_types_are_offered(self):
        routine = Task(
            title="근태 현황 점검",
            department=self.department,
            assignee=self.admin,
            start_date=date(2026, 9, 4),
            target_date=date(2026, 9, 4),
            status="진행중",
            progress=0,
            repeat_cycle="일간",
            creator=self.admin,
        )
        routine.classifications.append(TaskClassification(name="루틴"))
        db.session.add(routine)
        db.session.commit()
        response = self.client.get("/meetings")
        self.assertIn("근태 현황 점검".encode(), response.data)
        self.assertIn("채용 프로세스 정비".encode(), response.data)
        self.assertIn("루틴·일반·주요·대표이사님 수명업무".encode(), response.data)

    def test_participants_must_be_approved_business_staff(self):
        other_department = Department(name="외부부서", active=True)
        db.session.add(other_department)
        db.session.flush()
        outsider = Employee(
            name="외부인원",
            department=other_department,
            position="팀원",
            login_id="outside1",
            password_hash="",
            status="재직",
            approval_status="승인완료",
            role=self.admin_role,
            must_change_password=False,
        )
        outsider.set_password("Outside123")
        db.session.add(outsider)
        db.session.commit()
        response = self.client.post(
            "/meetings",
            data={
                "document_type": "agenda",
                "meeting_date": "2026-09-04",
                "author_id": str(outsider.id),
                "reporter_id": str(self.admin.id),
                "attendee_ids": [str(self.admin.id)],
                "task_ids": [str(self.task.id)],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("경영사업본부 재직 임직원".encode(), response.data)
        self.assertEqual(db.session.scalar(db.select(db.func.count(DailyMeeting.id))), 0)

    def test_excel_download_populates_original_template_without_dropping_media(self):
        meeting = DailyMeeting(
            meeting_date=date(2026, 9, 4),
            document_type="agenda",
            title="경영 일일회의 아젠다",
            agenda_content="채용 일정 확인",
            discussion_notes="공고 게시 전 최종 검토",
            decisions="금일 공고 게시",
            action_items="관리자: 오후 3시까지 게시",
            special_notes="신규 입사자 좌석 확인",
            duration_minutes=30,
            author=self.admin,
            reporter=self.admin,
            creator=self.admin,
            department=self.department,
            attendees=[self.admin],
            tasks=[self.task],
        )
        db.session.add(meeting)
        db.session.commit()
        response = self.client.get(f"/meetings/{meeting.id}/excel")
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response.content_type)
        with zipfile.ZipFile(io.BytesIO(response.data)) as workbook:
            media = sorted(name for name in workbook.namelist() if name.startswith("xl/media/"))
            sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
            parsed_sheet = ElementTree.fromstring(sheet_xml)
            self.assertEqual(
                media,
                [
                    "xl/media/image1.emf",
                    "xl/media/image2.jpg",
                    "xl/media/image3.emf",
                    "xl/media/image4.emf",
                ],
            )
            self.assertIn("경영 일일회의 아젠다_09/04(금)", sheet_xml)
            self.assertIn("인사총무팀 / 관리자 부서장", sheet_xml)
            self.assertIn("채용 프로세스 정비", sheet_xml)
            self.assertIn("신규 입사자 좌석 확인", sheet_xml)
            self.assertEqual(
                len(parsed_sheet.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row")),
                129,
            )

    def test_png_export_uses_local_browser_rendering(self):
        with self.client.get("/static/app.js") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"downloadElementAsPng", response.data)
            self.assertIn(b'canvas.toBlob', response.data)
            self.assertNotIn(b"https://", response.data)


if __name__ == "__main__":
    unittest.main()

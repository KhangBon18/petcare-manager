"""Unit tests cho ExamService và ExamRepository."""

from pathlib import Path
import tempfile
import unittest

from petcare.database.initialize import initialize_database
from petcare.services.auth_service import AuthSession
from petcare.services.catalog_service import CatalogService
from petcare.services.exam_service import ExamService
from petcare.services.owner_service import OwnerService
from petcare.services.pet_service import PetService


class TestExamService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_exam.db"
        initialize_database(self.db_path)

        self.admin_session = AuthSession(user_id=1, username="admin", role="admin", full_name="Admin")
        self.staff_session = AuthSession(user_id=2, username="staff", role="staff", full_name="Nhân viên")

        self.owner_service = OwnerService(self.db_path)
        self.pet_service = PetService(self.db_path)
        self.catalog_service = CatalogService(self.db_path)
        self.exam_service = ExamService(self.db_path)

        # Tạo chủ nuôi, thú cưng và dịch vụ
        self.owner_id = self.owner_service.create_owner(
            self.staff_session,
            {"full_name": "Nguyễn Thị Lan", "phone": "0901234567", "address": "Quận 1"},
        )
        self.pet_id = self.pet_service.create_pet(
            self.staff_session,
            {"owner_id": self.owner_id, "name": "Miu", "species": "Mèo"},
        )
        self.service_id = self.catalog_service.create_service(
            self.admin_session,
            {"name": "Khám bệnh tổng quát", "category": "Khám bệnh", "price_vnd": 150000},
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_record_exam_creates_both_exam_and_visit(self):
        exam_id, visit_id = self.exam_service.record_exam(
            self.staff_session,
            {
                "pet_id": self.pet_id,
                "service_id": self.service_id,
                "exam_date": "2026-10-16",
                "symptoms": "Ho, sốt nhẹ",
                "diagnosis": "Viêm hô hấp trên",
                "medicines": "Kháng sinh uống 5 ngày",
            },
        )
        self.assertIsInstance(exam_id, int)
        self.assertIsInstance(visit_id, int)

        exam = self.exam_service.get_exam(self.staff_session, exam_id)
        self.assertIsNotNone(exam)
        self.assertEqual(exam["visit_id"], visit_id)
        self.assertEqual(exam["symptoms"], "Ho, sốt nhẹ")
        self.assertEqual(exam["unit_price_vnd"], 150000)

    def test_catalog_price_change_does_not_modify_past_visit(self):
        # 1. Ghi nhận ca khám lúc giá 150.000
        exam_id, visit_id = self.exam_service.record_exam(
            self.staff_session,
            {
                "pet_id": self.pet_id,
                "service_id": self.service_id,
                "exam_date": "2026-10-16",
                "symptoms": "Kén ăn",
                "diagnosis": "Đầy hơi",
                "medicines": "Men tiêu hóa",
            },
        )

        # 2. Admin đổi giá dịch vụ lên 250.000
        self.catalog_service.update_service(
            self.admin_session,
            self.service_id,
            {"name": "Khám bệnh tổng quát", "category": "Khám bệnh", "price_vnd": 250000},
        )

        # 3. Ca khám cũ vẫn giữ giá 150.000
        exam = self.exam_service.get_exam(self.staff_session, exam_id)
        self.assertEqual(exam["unit_price_vnd"], 150000)

    def test_record_exam_validation_errors(self):
        # Thú cưng không tồn tại
        with self.assertRaises(ValueError):
            self.exam_service.record_exam(
                self.staff_session,
                {
                    "pet_id": 9999,
                    "service_id": self.service_id,
                    "symptoms": "Sốt",
                    "diagnosis": "Cảm cúm",
                },
            )

        # Triệu chứng để trống
        with self.assertRaises(ValueError):
            self.exam_service.record_exam(
                self.staff_session,
                {
                    "pet_id": self.pet_id,
                    "service_id": self.service_id,
                    "symptoms": "",
                    "diagnosis": "Cảm cúm",
                },
            )


if __name__ == "__main__":
    unittest.main()

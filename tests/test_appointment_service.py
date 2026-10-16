"""Unit tests cho AppointmentService và AppointmentRepository."""

from pathlib import Path
import tempfile
import unittest

from petcare.database.connection import get_connection
from petcare.database.initialize import initialize_database
from petcare.services.appointment_service import AppointmentService
from petcare.services.auth_service import AuthSession
from petcare.services.owner_service import OwnerService
from petcare.services.pet_service import PetService


class TestAppointmentService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_appt.db"
        initialize_database(self.db_path)

        self.staff_session = AuthSession(user_id=2, username="staff", role="staff", full_name="Nhân viên")

        self.owner_service = OwnerService(self.db_path)
        self.pet_service = PetService(self.db_path)
        self.appointment_service = AppointmentService(self.db_path)

        self.owner_id = self.owner_service.create_owner(
            self.staff_session,
            {"full_name": "Nguyễn Thị Lan", "phone": "0901234567", "address": "Quận 1"},
        )
        self.pet_id = self.pet_service.create_pet(
            self.staff_session,
            {"owner_id": self.owner_id, "name": "Miu", "species": "Mèo"},
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_appointment_does_not_create_fee(self):
        appt_id = self.appointment_service.create_appointment(
            self.staff_session,
            {
                "pet_id": self.pet_id,
                "type": "Khám định kỳ",
                "scheduled_at": "2026-10-25 09:00",
                "note": "Khám răng miệng cho mèo Miu",
            },
        )
        self.assertIsInstance(appt_id, int)
        self.assertGreater(appt_id, 0)

        # Kiểm tra trực tiếp trong DB: không có bản ghi service_visits nào được tạo
        conn = get_connection(self.db_path)
        visits_count = conn.execute("SELECT COUNT(*) as cnt FROM service_visits").fetchone()["cnt"]
        conn.close()
        self.assertEqual(visits_count, 0, "Lịch hẹn không được tự động phát sinh phí hoặc tạo lượt dịch vụ")

    def test_update_status(self):
        appt_id = self.appointment_service.create_appointment(
            self.staff_session,
            {
                "pet_id": self.pet_id,
                "type": "Tắm spa",
                "scheduled_at": "2026-10-26 14:00",
            },
        )
        success = self.appointment_service.update_status(self.staff_session, appt_id, "completed")
        self.assertTrue(success)

        appt = self.appointment_service.get_appointment(self.staff_session, appt_id)
        self.assertEqual(appt["status"], "completed")

        with self.assertRaises(ValueError):
            self.appointment_service.update_status(self.staff_session, appt_id, "invalid_status")


if __name__ == "__main__":
    unittest.main()

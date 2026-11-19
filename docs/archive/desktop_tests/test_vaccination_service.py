"""Unit tests cho VaccinationService và VaccinationRepository."""

from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

from petcare.database.initialize import initialize_database
from petcare.services.auth_service import AuthSession
from petcare.services.catalog_service import CatalogService
from petcare.services.owner_service import OwnerService
from petcare.services.pet_service import PetService
from petcare.services.vaccination_service import VaccinationService


class TestVaccinationService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_vaccination.db"
        initialize_database(self.db_path)

        self.admin_session = AuthSession(user_id=1, username="admin", role="admin", full_name="Admin")
        self.staff_session = AuthSession(user_id=2, username="staff", role="staff", full_name="Nhân viên")

        self.owner_service = OwnerService(self.db_path)
        self.pet_service = PetService(self.db_path)
        self.catalog_service = CatalogService(self.db_path)
        self.vaccination_service = VaccinationService(self.db_path)

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
            {"name": "Tiêm vaccine Dại", "category": "Tiêm phòng", "price_vnd": 180000},
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_record_vaccination_success(self):
        today_str = date.today().isoformat()
        next_due = (date.today() + timedelta(days=365)).isoformat()

        vac_id, visit_id = self.vaccination_service.record_vaccination(
            self.staff_session,
            {
                "pet_id": self.pet_id,
                "service_id": self.service_id,
                "vaccine_name": "Rabisin",
                "injection_date": today_str,
                "next_due_date": next_due,
            },
        )
        self.assertIsInstance(vac_id, int)
        self.assertIsInstance(visit_id, int)

        vac = self.vaccination_service.get_vaccination(self.staff_session, vac_id)
        self.assertIsNotNone(vac)
        self.assertEqual(vac["visit_id"], visit_id)
        self.assertEqual(vac["vaccine_name"], "Rabisin")
        self.assertEqual(vac["unit_price_vnd"], 180000)

    def test_invalid_dates_rejected(self):
        today_str = date.today().isoformat()
        past_due = (date.today() - timedelta(days=10)).isoformat()

        # Ngày hẹn nhắc lại trước hoặc bằng ngày tiêm
        with self.assertRaises(ValueError):
            self.vaccination_service.record_vaccination(
                self.staff_session,
                {
                    "pet_id": self.pet_id,
                    "service_id": self.service_id,
                    "vaccine_name": "Rabisin",
                    "injection_date": today_str,
                    "next_due_date": past_due,
                },
            )

        # Ngày tiêm ở tương lai
        future_inj = (date.today() + timedelta(days=2)).isoformat()
        with self.assertRaises(ValueError):
            self.vaccination_service.record_vaccination(
                self.staff_session,
                {
                    "pet_id": self.pet_id,
                    "service_id": self.service_id,
                    "vaccine_name": "Rabisin",
                    "injection_date": future_inj,
                },
            )

    def test_reminder_query_and_resolve(self):
        today_str = date.today().isoformat()
        due_soon = (date.today() + timedelta(days=15)).isoformat()

        vac_id, _ = self.vaccination_service.record_vaccination(
            self.staff_session,
            {
                "pet_id": self.pet_id,
                "service_id": self.service_id,
                "vaccine_name": "Vaccine 4 bệnh mèo",
                "injection_date": today_str,
                "next_due_date": due_soon,
            },
        )

        reminders = self.vaccination_service.get_upcoming_reminders(self.staff_session, days_ahead=30)
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0]["id"], vac_id)

        # Đánh dấu đã xử lý nhắc nhở
        self.vaccination_service.resolve_reminder(self.staff_session, vac_id)
        reminders_after = self.vaccination_service.get_upcoming_reminders(self.staff_session, days_ahead=30)
        self.assertEqual(len(reminders_after), 0)


if __name__ == "__main__":
    unittest.main()

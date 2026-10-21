"""Unit tests cho PetService và PetRepository."""

from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

from petcare.database.connection import get_connection
from petcare.database.initialize import initialize_database
from petcare.services.auth_service import AuthSession
from petcare.services.owner_service import OwnerService
from petcare.services.pet_service import PetService


class TestPetService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_petcare.db"
        initialize_database(self.db_path)
        self.owner_service = OwnerService(self.db_path)
        self.pet_service = PetService(self.db_path)
        self.staff_session = AuthSession(user_id=2, username="staff", role="staff", full_name="Nhân viên")

        # Tạo sẵn chủ nuôi
        self.owner_id = self.owner_service.create_owner(
            self.staff_session,
            {"full_name": "Nguyễn Thị Lan", "phone": "0901234567", "address": "Quận 1, TP.HCM"},
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_pet_success(self):
        pet_id = self.pet_service.create_pet(
            self.staff_session,
            {
                "owner_id": self.owner_id,
                "name": "Miu",
                "species": "Mèo",
                "breed": "Anh lông ngắn",
                "sex": "female",
                "birth_date": "2024-01-15",
                "weight_kg": 3.2,
                "coat_color": "Xám tro",
            },
        )
        self.assertIsInstance(pet_id, int)
        self.assertGreater(pet_id, 0)

        pet = self.pet_service.get_pet(self.staff_session, pet_id)
        self.assertIsNotNone(pet)
        self.assertEqual(pet["name"], "Miu")
        self.assertEqual(pet["species"], "Mèo")
        self.assertEqual(pet["weight_kg"], 3.2)
        self.assertEqual(pet["owner_name"], "Nguyễn Thị Lan")

    def test_create_pet_nonexistent_or_inactive_owner(self):
        # Chủ không tồn tại
        with self.assertRaises(ValueError):
            self.pet_service.create_pet(
                self.staff_session,
                {"owner_id": 9999, "name": "Bông", "species": "Chó"},
            )

        # Chủ đã ngừng hoạt động
        self.owner_service.delete_or_deactivate_owner(self.staff_session, self.owner_id)
        with self.assertRaises(ValueError):
            self.pet_service.create_pet(
                self.staff_session,
                {"owner_id": self.owner_id, "name": "Bông", "species": "Chó"},
            )

    def test_create_pet_validation_errors(self):
        # Tên trống
        with self.assertRaises(ValueError):
            self.pet_service.create_pet(
                self.staff_session,
                {"owner_id": self.owner_id, "name": "", "species": "Chó"},
            )

        # Cân nặng âm
        with self.assertRaises(ValueError):
            self.pet_service.create_pet(
                self.staff_session,
                {"owner_id": self.owner_id, "name": "Ki", "species": "Chó", "weight_kg": -2.5},
            )

        # Ngày sinh tương lai
        future_date = (date.today() + timedelta(days=30)).isoformat()
        with self.assertRaises(ValueError):
            self.pet_service.create_pet(
                self.staff_session,
                {"owner_id": self.owner_id, "name": "Ki", "species": "Chó", "birth_date": future_date},
            )

    def test_search_and_filter_pets(self):
        self.pet_service.create_pet(
            self.staff_session,
            {"owner_id": self.owner_id, "name": "Miu", "species": "Mèo", "breed": "Anh lông ngắn"},
        )
        self.pet_service.create_pet(
            self.staff_session,
            {"owner_id": self.owner_id, "name": "Lu", "species": "Chó", "breed": "Poodle"},
        )

        meo_list = self.pet_service.search_pets(self.staff_session, species="Mèo")
        self.assertEqual(len(meo_list), 1)
        self.assertEqual(meo_list[0]["name"], "Miu")

        kw_list = self.pet_service.search_pets(self.staff_session, keyword="Poodle")
        self.assertEqual(len(kw_list), 1)
        self.assertEqual(kw_list[0]["name"], "Lu")

    def test_delete_or_deactivate_pet(self):
        pet_id = self.pet_service.create_pet(
            self.staff_session,
            {"owner_id": self.owner_id, "name": "Miu Miu", "species": "Mèo"},
        )
        # Chưa có lịch sử -> xóa thật
        status = self.pet_service.delete_or_deactivate_pet(self.staff_session, pet_id)
        self.assertEqual(status, "deleted")
        self.assertIsNone(self.pet_service.get_pet(self.staff_session, pet_id))

        # Thú cưng có lịch sử dịch vụ -> chỉ deactivate
        pet_id2 = self.pet_service.create_pet(
            self.staff_session,
            {"owner_id": self.owner_id, "name": "Cún Cưng", "species": "Chó"},
        )
        conn = get_connection(self.db_path)
        # Giả lập 1 lịch hẹn
        conn.execute(
            """
            INSERT INTO appointments (pet_id, type, scheduled_at, status, created_at)
            VALUES (?, 'Khám bệnh', '2026-10-20', 'planned', '2026-10-16')
            """,
            (pet_id2,),
        )
        conn.commit()
        conn.close()

        status2 = self.pet_service.delete_or_deactivate_pet(self.staff_session, pet_id2)
        self.assertEqual(status2, "deactivated")

        pet2 = self.pet_service.get_pet(self.staff_session, pet_id2)
        self.assertIsNotNone(pet2)
        self.assertEqual(pet2["active"], 0)


if __name__ == "__main__":
    unittest.main()

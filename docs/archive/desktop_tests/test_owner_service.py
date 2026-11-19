"""Unit tests cho OwnerService và OwnerRepository."""

from pathlib import Path
import tempfile
import unittest

from petcare.database.connection import get_connection
from petcare.database.initialize import initialize_database
from petcare.services.auth_service import AuthSession
from petcare.services.owner_service import OwnerService
from petcare.services.pet_service import PetService


class TestOwnerService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_petcare.db"
        initialize_database(self.db_path)
        self.owner_service = OwnerService(self.db_path)
        self.pet_service = PetService(self.db_path)
        self.admin_session = AuthSession(user_id=1, username="admin", role="admin", full_name="Admin")
        self.staff_session = AuthSession(user_id=2, username="staff", role="staff", full_name="Nhân viên")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_owner_success(self):
        owner_id = self.owner_service.create_owner(
            self.staff_session,
            {"full_name": "Nguyễn Thị Lan", "phone": "0901234567", "address": "123 Lê Lợi, Q1"},
        )
        self.assertIsInstance(owner_id, int)
        self.assertGreater(owner_id, 0)

        owner = self.owner_service.get_owner(self.staff_session, owner_id)
        self.assertIsNotNone(owner)
        self.assertEqual(owner["full_name"], "Nguyễn Thị Lan")
        self.assertEqual(owner["phone"], "0901234567")
        self.assertEqual(owner["active"], 1)

    def test_create_owner_validation_failure(self):
        # Tên trống
        with self.assertRaises(ValueError):
            self.owner_service.create_owner(
                self.staff_session,
                {"full_name": "", "phone": "0901234567", "address": "123 Lê Lợi"},
            )

        # Số điện thoại không hợp lệ
        with self.assertRaises(ValueError):
            self.owner_service.create_owner(
                self.staff_session,
                {"full_name": "Trần Văn A", "phone": "123", "address": "123 Lê Lợi"},
            )

        # Địa chỉ trống
        with self.assertRaises(ValueError):
            self.owner_service.create_owner(
                self.staff_session,
                {"full_name": "Trần Văn A", "phone": "0901234567", "address": ""},
            )

    def test_update_owner(self):
        owner_id = self.owner_service.create_owner(
            self.staff_session,
            {"full_name": "Nguyễn Văn B", "phone": "0988888888", "address": "Hà Nội"},
        )
        success = self.owner_service.update_owner(
            self.staff_session,
            owner_id,
            {"full_name": "Nguyễn Văn B (đã đổi)", "phone": "0988888889", "address": "TP.HCM", "active": 1},
        )
        self.assertTrue(success)

        updated = self.owner_service.get_owner(self.staff_session, owner_id)
        self.assertEqual(updated["full_name"], "Nguyễn Văn B (đã đổi)")
        self.assertEqual(updated["phone"], "0988888889")
        self.assertEqual(updated["address"], "TP.HCM")

    def test_search_and_list_owners(self):
        self.owner_service.create_owner(
            self.staff_session,
            {"full_name": "Nguyễn Thị Lan", "phone": "0901234567", "address": "Quận 1"},
        )
        self.owner_service.create_owner(
            self.staff_session,
            {"full_name": "Trần Văn Minh", "phone": "0912345678", "address": "Quận 3"},
        )

        results = self.owner_service.search_owners(self.staff_session, keyword="Lan")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["full_name"], "Nguyễn Thị Lan")

        all_owners = self.owner_service.list_owners(self.staff_session)
        self.assertEqual(len(all_owners), 2)

    def test_delete_vs_deactivate_owner(self):
        # Chủ không có thú cưng -> xóa hoàn toàn
        owner_id = self.owner_service.create_owner(
            self.staff_session,
            {"full_name": "Chủ Trống", "phone": "0999999999", "address": "Cần Thơ"},
        )
        result = self.owner_service.delete_or_deactivate_owner(self.staff_session, owner_id)
        self.assertEqual(result, "deleted")
        self.assertIsNone(self.owner_service.get_owner(self.staff_session, owner_id))

        # Chủ có thú cưng -> chuyển sang ngừng theo dõi (deactivated)
        owner_id2 = self.owner_service.create_owner(
            self.staff_session,
            {"full_name": "Chị Lan Có Mèo", "phone": "0901112233", "address": "Đà Nẵng"},
        )
        self.pet_service.create_pet(
            self.staff_session,
            {"owner_id": owner_id2, "name": "Miu", "species": "Mèo", "sex": "female"},
        )
        result2 = self.owner_service.delete_or_deactivate_owner(self.staff_session, owner_id2)
        self.assertEqual(result2, "deactivated")

        owner2 = self.owner_service.get_owner(self.staff_session, owner_id2)
        self.assertIsNotNone(owner2)
        self.assertEqual(owner2["active"], 0)


if __name__ == "__main__":
    unittest.main()

"""Unit tests cho CatalogService và CatalogRepository."""

from pathlib import Path
import tempfile
import unittest

from petcare.database.initialize import initialize_database
from petcare.services.auth_service import AuthSession
from petcare.services.catalog_service import CatalogService


class TestCatalogService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_catalog.db"
        initialize_database(self.db_path)
        self.catalog_service = CatalogService(self.db_path)
        self.admin_session = AuthSession(user_id=1, username="admin", role="admin", full_name="Admin")
        self.staff_session = AuthSession(user_id=2, username="staff", role="staff", full_name="Nhân viên")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_admin_create_service_success(self):
        service_id = self.catalog_service.create_service(
            self.admin_session,
            {"name": "Khám chuyên khoa mắt", "category": "Khám bệnh", "price_vnd": 200000},
        )
        self.assertIsInstance(service_id, int)
        self.assertGreater(service_id, 0)

        svc = self.catalog_service.get_service(self.staff_session, service_id)
        self.assertIsNotNone(svc)
        self.assertEqual(svc["name"], "Khám chuyên khoa mắt")
        self.assertEqual(svc["price_vnd"], 200000)

    def test_staff_cannot_create_or_update_service(self):
        # Staff tạo mới bị chặn
        with self.assertRaises(PermissionError):
            self.catalog_service.create_service(
                self.staff_session,
                {"name": "Dịch vụ trái phép", "category": "Khám bệnh", "price_vnd": 100000},
            )

        # Tạo sẵn bằng admin
        service_id = self.catalog_service.create_service(
            self.admin_session,
            {"name": "Cắt móng", "category": "Chăm sóc", "price_vnd": 50000},
        )

        # Staff cố tình đổi giá bị chặn
        with self.assertRaises(PermissionError):
            self.catalog_service.update_service(
                self.staff_session,
                service_id,
                {"name": "Cắt móng", "category": "Chăm sóc", "price_vnd": 60000},
            )

    def test_create_service_validation_errors(self):
        # Tên trống
        with self.assertRaises(ValueError):
            self.catalog_service.create_service(
                self.admin_session,
                {"name": "", "category": "Khám bệnh", "price_vnd": 100000},
            )

        # Giá âm
        with self.assertRaises(ValueError):
            self.catalog_service.create_service(
                self.admin_session,
                {"name": "Dịch vụ giá âm", "category": "Khám bệnh", "price_vnd": -50000},
            )

        # Trùng tên dịch vụ
        self.catalog_service.create_service(
            self.admin_session,
            {"name": "Tẩy giun", "category": "Chăm sóc", "price_vnd": 50000},
        )
        with self.assertRaises(ValueError):
            self.catalog_service.create_service(
                self.admin_session,
                {"name": "Tẩy giun", "category": "Chăm sóc", "price_vnd": 70000},
            )


if __name__ == "__main__":
    unittest.main()

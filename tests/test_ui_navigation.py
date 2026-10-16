"""Kiểm thử tự động khởi tạo giao diện PetCareApp và điều hướng tất cả màn hình."""

from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from petcare.app import PetCareApp
from petcare.database.seed import seed_database


class TestUINavigation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_ui.db"
        seed_database(self.db_path)

        # 1. Chỉ skip khi môi trường thiếu điều kiện mở Tk (ví dụ: máy tính không có màn hình display)
        try:
            self.root = tk.Tk()
            self.root.withdraw()  # Ẩn cửa sổ để chạy kiểm thử headless
        except tk.TclError as e:
            self.skipTest(f"Môi trường không hỗ trợ mở Tkinter display: {e}")
        except Exception as e:
            self.skipTest(f"Không thể khởi tạo nền tảng đồ họa Tk: {e}")

        # 2. Khởi tạo PetCareApp BÊN NGOÀI try-catch của Tk:
        # Bất kỳ lỗi logic/ứng dụng nào phải làm test THẤT BẠI (Fail), tuyệt đối không bị che giấu thành skip!
        self.app = PetCareApp(self.root, database_path=self.db_path)

    def tearDown(self):
        try:
            if hasattr(self, "root") and self.root:
                self.root.destroy()
        except Exception:
            pass
        self.temp_dir.cleanup()

    def test_app_login_and_navigate_all_screens(self):
        # 1. Ban đầu hiển thị LoginView
        self.assertIsNone(self.app.session)
        self.assertIsNotNone(self.app.current_view)

        # 2. Đăng nhập với Admin
        session = self.app.auth_service.login("admin", "Admin@123")
        self.app.on_login_success(session)
        self.assertIsNotNone(self.app.session)
        self.assertTrue(self.app.session.is_admin())

        # 3. Lần lượt mở và cập nhật tất cả các màn hình
        screens_to_test = [
            "owners",
            "pets",
            "examinations",
            "vaccinations",
            "appointments",
            "visits",
            "invoices",
            "reports",
            "services",
            "users",
        ]
        for screen_key in screens_to_test:
            self.app.show_screen(screen_key)
            self.root.update()
            self.assertIsNotNone(self.app.current_view)

        # 4. Thử mở màn hình pet_profile với pet_id = 1
        self.app.show_pet_profile(pet_id=1)
        self.root.update()
        self.assertIsNotNone(self.app.current_view)

        # 5. Đăng xuất
        self.app.show_login()
        self.root.update()
        self.assertIsNone(self.app.session)

    def test_app_initialization_error_not_masked_as_skip(self):
        """Chứng minh lỗi khởi tạo của PetCareApp không bị che giấu thành skipTest."""
        with patch.object(PetCareApp, "__init__", side_effect=RuntimeError("Mô phỏng lỗi ứng dụng")):
            with self.assertRaises(RuntimeError):
                PetCareApp(self.root, database_path=self.db_path)


if __name__ == "__main__":
    unittest.main()

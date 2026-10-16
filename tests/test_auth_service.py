"""Unit tests cho AuthService và UserRepository."""

from pathlib import Path
import tempfile
import unittest

from petcare.database.initialize import initialize_database
from petcare.database.seed import seed_database
from petcare.services.auth_service import AuthService, AuthSession


class TestAuthService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_auth.db"
        seed_database(self.db_path)
        self.auth_service = AuthService(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_login_admin_success(self):
        session = self.auth_service.login("admin", "Admin@123")
        self.assertIsInstance(session, AuthSession)
        self.assertEqual(session.username, "admin")
        self.assertEqual(session.role, "admin")
        self.assertTrue(session.is_admin())
        self.assertTrue(session.is_staff())

    def test_login_staff_success(self):
        session = self.auth_service.login("staff1", "Staff@123")
        self.assertIsInstance(session, AuthSession)
        self.assertEqual(session.username, "staff1")
        self.assertEqual(session.role, "staff")
        self.assertFalse(session.is_admin())
        self.assertTrue(session.is_staff())

    def test_login_failure(self):
        # Mật khẩu sai
        with self.assertRaises(ValueError):
            self.auth_service.login("admin", "WrongPassword")

        # Tài khoản không tồn tại
        with self.assertRaises(ValueError):
            self.auth_service.login("non_existent", "Password123")

        # Để trống
        with self.assertRaises(ValueError):
            self.auth_service.login("", "")

    def test_admin_create_user(self):
        admin_session = self.auth_service.login("admin", "Admin@123")
        staff_session = self.auth_service.login("staff1", "Staff@123")

        # Admin tạo được nhân viên mới
        new_user_id = self.auth_service.create_user(
            admin_session,
            username="staff_new",
            password="NewStaff@123",
            role="staff",
            full_name="Nhân viên mới",
        )
        self.assertIsInstance(new_user_id, int)
        self.assertGreater(new_user_id, 0)

        # Đăng nhập bằng tài khoản mới
        new_session = self.auth_service.login("staff_new", "NewStaff@123")
        self.assertEqual(new_session.username, "staff_new")

        # Staff tạo tài khoản thì bị chặn
        with self.assertRaises(PermissionError):
            self.auth_service.create_user(
                staff_session,
                username="hacker",
                password="Password123",
                role="admin",
                full_name="Kẻ tấn công",
            )

    def test_cannot_deactivate_or_demote_last_admin(self):
        admin_session = self.auth_service.login("admin", "Admin@123")
        # Hệ thống chỉ có 1 admin duy nhất trong seed
        with self.assertRaises(ValueError):
            # Cố tình hạ quyền xuống staff
            self.auth_service.update_user(
                admin_session,
                user_id=admin_session.user_id,
                full_name="Admin",
                role="staff",
                active=1,
            )

        with self.assertRaises(ValueError):
            # Cố tình khóa tài khoản
            self.auth_service.update_user(
                admin_session,
                user_id=admin_session.user_id,
                full_name="Admin",
                role="admin",
                active=0,
            )


if __name__ == "__main__":
    unittest.main()

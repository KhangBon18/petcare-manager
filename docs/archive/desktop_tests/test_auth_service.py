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

    def test_logged_in_staff_deactivated_is_blocked(self):
        """QC Lỗi 1: Nhân viên đang đăng nhập, khi tài khoản bị khóa trong DB thì mọi thao tác sau đó phải bị chặn."""
        from petcare.services.owner_service import OwnerService
        owner_service = OwnerService(self.db_path)
        admin_session = self.auth_service.login("admin", "Admin@123")
        staff_session = self.auth_service.login("staff1", "Staff@123")

        # Thao tác ban đầu thành công
        owner_id = owner_service.create_owner(
            staff_session,
            {"full_name": "Khách ban đầu", "phone": "0987654321", "address": "Quận 3"},
        )
        self.assertGreater(owner_id, 0)

        # Admin khóa tài khoản staff1 trong DB
        self.auth_service.update_user(
            admin_session,
            user_id=staff_session.user_id,
            full_name=staff_session.full_name,
            role="staff",
            active=0,
        )

        # Phiên staff cũ cố thực hiện nghiệp vụ tiếp theo phải bị chặn ngay lập tức
        with self.assertRaises(PermissionError) as ctx:
            owner_service.create_owner(
                staff_session,
                {"full_name": "Khách bị chặn", "phone": "0912345678", "address": "Quận 5"},
            )
        self.assertIn("khóa", str(ctx.exception))

    def test_logged_in_admin_demoted_is_blocked(self):
        """QC Lỗi 1: Admin đang đăng nhập, khi bị hạ quyền xuống staff trong DB thì các thao tác admin sau đó phải bị chặn."""
        from petcare.services.catalog_service import CatalogService
        catalog_service = CatalogService(self.db_path)
        admin1_session = self.auth_service.login("admin", "Admin@123")

        # Tạo thêm admin thứ 2
        admin2_id = self.auth_service.create_user(
            admin1_session,
            username="admin2",
            password="Admin2@123",
            role="admin",
            full_name="Quản Trị Viên 2",
        )
        admin2_session = self.auth_service.login("admin2", "Admin2@123")
        self.assertTrue(admin2_session.is_admin())

        # Admin 2 tạo dịch vụ thành công khi còn quyền
        svc_id = catalog_service.create_service(
            admin2_session,
            {"name": "Dịch vụ thử nghiệm", "category": "Khám bệnh", "price_vnd": 120000},
        )
        self.assertGreater(svc_id, 0)

        # Admin 1 hạ quyền Admin 2 xuống 'staff'
        self.auth_service.update_user(
            admin1_session,
            user_id=admin2_id,
            full_name="Quản Trị Viên 2",
            role="staff",
            active=1,
        )

        # Phiên cũ của Admin 2 (vẫn giữ role='admin' trong object) cố thực hiện thao tác quản trị phải bị chặn
        with self.assertRaises(PermissionError) as ctx:
            self.auth_service.create_user(
                admin2_session,
                username="hacker2",
                password="Password123",
                role="staff",
                full_name="Tấn công",
            )
        self.assertIn("Quản trị viên", str(ctx.exception))

        with self.assertRaises(PermissionError) as ctx:
            catalog_service.create_service(
                admin2_session,
                {"name": "Dịch vụ trái phép", "category": "Khám bệnh", "price_vnd": 500000},
            )
        self.assertIn("Quản trị viên", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

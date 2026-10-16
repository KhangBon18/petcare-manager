"""Bộ điều khiển ứng dụng chính PetCareApp: một Tk root, phiên đăng nhập và điều hướng Frame."""

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from petcare.database.initialize import initialize_database
from petcare.services.appointment_service import AppointmentService
from petcare.services.auth_service import AuthService, AuthSession
from petcare.services.catalog_service import CatalogService
from petcare.services.exam_service import ExamService
from petcare.services.invoice_service import InvoiceService
from petcare.services.owner_service import OwnerService
from petcare.services.pet_service import PetService
from petcare.services.report_service import ReportService
from petcare.services.vaccination_service import VaccinationService
from petcare.services.visit_service import VisitService
from petcare.ui.appointments_view import AppointmentsView
from petcare.ui.common import show_confirm
from petcare.ui.examinations_view import ExaminationsView
from petcare.ui.invoices_view import InvoicesView
from petcare.ui.login_view import LoginView
from petcare.ui.owners_view import OwnersView
from petcare.ui.pet_profile_view import PetProfileView
from petcare.ui.pets_view import PetsView
from petcare.ui.reports_view import ReportsView
from petcare.ui.services_view import ServicesView
from petcare.ui.theme import apply_theme, COLOR_CARD, COLOR_PRIMARY, COLOR_BORDER
from petcare.ui.users_view import UsersView
from petcare.ui.vaccinations_view import VaccinationsView
from petcare.ui.visits_view import VisitsView


class PetCareApp:
    """Quản lý một cửa sổ gốc Tk, các dịch vụ nghiệp vụ, phiên đăng nhập và điều hướng."""

    def __init__(self, root: tk.Tk, database_path: Path | str | None = None):
        self.root = root
        self.database_path = database_path

        # Tự động đảm bảo cơ sở dữ liệu đã có cấu trúc bảng
        initialize_database(self.database_path)

        # Khởi tạo các services
        self.auth_service = AuthService(self.database_path)
        self.owner_service = OwnerService(self.database_path)
        self.pet_service = PetService(self.database_path)
        self.catalog_service = CatalogService(self.database_path)
        self.exam_service = ExamService(self.database_path)
        self.vaccination_service = VaccinationService(self.database_path)
        self.appointment_service = AppointmentService(self.database_path)
        self.visit_service = VisitService(self.database_path)
        self.invoice_service = InvoiceService(self.database_path)
        self.report_service = ReportService(self.database_path)

        # Cấu hình cửa sổ chính
        self.root.title("PetCare Manager — Quản lý Phòng khám Thú cưng")
        self.root.geometry("1120x720")
        self.root.minsize(980, 640)
        apply_theme(self.root)

        # Trạng thái phiên
        self.session: AuthSession | None = None
        self.current_shell: ttk.Frame | None = None
        self.current_view: ttk.Frame | None = None
        self.content_frame: ttk.Frame | None = None
        self.nav_buttons: dict[str, ttk.Button] = {}

        # Mở màn hình đăng nhập đầu tiên
        self.show_login()

    def show_login(self) -> None:
        """Hiển thị màn hình đăng nhập."""
        if self.current_shell is not None:
            self.current_shell.destroy()
            self.current_shell = None

        if self.current_view is not None:
            self.current_view.destroy()
            self.current_view = None

        self.session = None
        self.current_view = LoginView(
            self.root,
            auth_service=self.auth_service,
            on_login_success=self.on_login_success,
        )
        self.current_view.pack(fill="both", expand=True)

    def on_login_success(self, session: AuthSession) -> None:
        """Xử lý sau khi người dùng xác thực thành công."""
        self.session = session
        if self.current_view is not None:
            self.current_view.destroy()
            self.current_view = None

        self.build_main_layout()
        self.show_screen("owners")

    def build_main_layout(self) -> None:
        """Xây dựng khung giao diện chính với thanh điều hướng bên trái và vùng nội dung bên phải."""
        self.current_shell = ttk.Frame(self.root)
        self.current_shell.pack(fill="both", expand=True)

        # Sidebar điều hướng bên trái
        sidebar = ttk.Frame(self.current_shell, padding=12, style="Card.TFrame")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        sidebar.config(width=220)

        # Logo / Tiêu đề thương hiệu
        ttk.Label(
            sidebar,
            text="🐾 PetCare",
            font=("Segoe UI", 16, "bold"),
            foreground=COLOR_PRIMARY,
            style="Card.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        ttk.Label(
            sidebar,
            text="Manager System",
            style="Muted.TLabel",
            background=COLOR_CARD,
        ).pack(anchor="w", pady=(0, 16))

        # Thông tin tài khoản người dùng đang đăng nhập
        user_card = ttk.Frame(sidebar, padding=8, relief="solid", borderwidth=1)
        user_card.pack(fill="x", pady=(0, 16))

        role_label = "Quản trị viên" if self.session and self.session.is_admin() else "Nhân viên"
        user_name = self.session.full_name if self.session else "Khách"

        ttk.Label(user_card, text=f"👤 {user_name}", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Label(user_card, text=f"Vai trò: {role_label}", style="Muted.TLabel").pack(anchor="w")

        # Danh mục màn hình điều hướng
        nav_items = [
            ("owners", "🐾 Chủ nuôi"),
            ("pets", "🐶 Thú cưng"),
            ("examinations", "🩺 Khám bệnh"),
            ("vaccinations", "💉 Tiêm phòng"),
            ("appointments", "📅 Lịch hẹn"),
            ("visits", "📋 Lượt dịch vụ"),
            ("invoices", "💳 Hóa đơn"),
            ("reports", "📊 Thống kê"),
            ("services", "⚙️ Bảng giá"),
        ]

        # Chỉ Admin mới thấy menu Quản lý tài khoản
        if self.session and self.session.is_admin():
            nav_items.append(("users", "👥 Tài khoản"))

        self.nav_buttons.clear()
        for screen_key, label in nav_items:
            btn = ttk.Button(
                sidebar,
                text=label,
                command=lambda k=screen_key: self.show_screen(k),
            )
            btn.pack(fill="x", pady=2)
            self.nav_buttons[screen_key] = btn

        # Khoảng trống đẩy nút Đăng xuất xuống đáy
        spacer = ttk.Frame(sidebar, style="Card.TFrame")
        spacer.pack(fill="both", expand=True)

        # Nút Đăng xuất và Thoát
        ttk.Button(
            sidebar,
            text="🚪 Đăng xuất",
            command=self.logout,
        ).pack(fill="x", pady=(0, 4))

        ttk.Button(
            sidebar,
            text="❌ Thoát",
            command=self.root.destroy,
        ).pack(fill="x")

        # Khung chứa nội dung chính
        self.content_frame = ttk.Frame(self.current_shell)
        self.content_frame.pack(side="left", fill="both", expand=True)

    def show_screen(self, screen_id: str, **kwargs) -> None:
        """Chuyển đổi màn hình hiển thị trong khung nội dung."""
        if self.content_frame is None or self.session is None:
            return

        if self.current_view is not None:
            self.current_view.destroy()
            self.current_view = None

        if screen_id == "owners":
            self.current_view = OwnersView(
                self.content_frame,
                owner_service=self.owner_service,
                session=self.session,
                on_view_owner_pets=self.show_owner_pets,
            )
        elif screen_id == "pets":
            self.current_view = PetsView(
                self.content_frame,
                pet_service=self.pet_service,
                owner_service=self.owner_service,
                session=self.session,
                on_view_pet_profile=self.show_pet_profile,
                initial_owner_id=kwargs.get("owner_id"),
            )
        elif screen_id == "pet_profile":
            pet_id = kwargs.get("pet_id")
            if not pet_id:
                self.show_screen("pets")
                return
            self.current_view = PetProfileView(
                self.content_frame,
                pet_id=pet_id,
                pet_service=self.pet_service,
                exam_service=self.exam_service,
                vaccination_service=self.vaccination_service,
                appointment_service=self.appointment_service,
                visit_service=self.visit_service,
                session=self.session,
                on_back=lambda: self.show_screen("pets"),
            )
        elif screen_id == "examinations":
            self.current_view = ExaminationsView(
                self.content_frame,
                exam_service=self.exam_service,
                pet_service=self.pet_service,
                catalog_service=self.catalog_service,
                session=self.session,
            )
        elif screen_id == "vaccinations":
            self.current_view = VaccinationsView(
                self.content_frame,
                vaccination_service=self.vaccination_service,
                pet_service=self.pet_service,
                catalog_service=self.catalog_service,
                session=self.session,
            )
        elif screen_id == "appointments":
            self.current_view = AppointmentsView(
                self.content_frame,
                appointment_service=self.appointment_service,
                pet_service=self.pet_service,
                session=self.session,
            )
        elif screen_id == "visits":
            self.current_view = VisitsView(
                self.content_frame,
                visit_service=self.visit_service,
                pet_service=self.pet_service,
                catalog_service=self.catalog_service,
                session=self.session,
            )
        elif screen_id == "invoices":
            self.current_view = InvoicesView(
                self.content_frame,
                invoice_service=self.invoice_service,
                visit_service=self.visit_service,
                owner_service=self.owner_service,
                session=self.session,
            )
        elif screen_id == "reports":
            self.current_view = ReportsView(
                self.content_frame,
                report_service=self.report_service,
                session=self.session,
            )
        elif screen_id == "services":
            self.current_view = ServicesView(
                self.content_frame,
                catalog_service=self.catalog_service,
                session=self.session,
            )
        elif screen_id == "users":
            self.current_view = UsersView(
                self.content_frame,
                auth_service=self.auth_service,
                session=self.session,
            )

        if self.current_view is not None:
            self.current_view.pack(fill="both", expand=True)

    def show_owner_pets(self, owner_id: int, owner_name: str) -> None:
        """Chuyển sang màn hình thú cưng và lọc theo chủ nuôi được chọn."""
        self.show_screen("pets", owner_id=owner_id)

    def show_pet_profile(self, pet_id: int) -> None:
        """Chuyển sang màn hình xem hồ sơ chi tiết của thú cưng."""
        self.show_screen("pet_profile", pet_id=pet_id)

    def logout(self) -> None:
        """Xác nhận và đăng xuất phiên làm việc."""
        if show_confirm("Đăng xuất", "Bạn có chắc chắn muốn đăng xuất khỏi hệ thống?"):
            self.show_login()


def run() -> None:
    """Khởi chạy ứng dụng Tkinter."""
    root = tk.Tk()
    PetCareApp(root)
    root.mainloop()

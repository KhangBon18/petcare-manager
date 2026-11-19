"""Màn hình quản lý tài khoản người dùng (UsersView - Chỉ Admin)."""

import tkinter as tk
from tkinter import simpledialog, ttk

from petcare.services.auth_service import AuthService, AuthSession
from petcare.ui.common import DataTable, HeaderBar, show_confirm, show_error, show_info


class UsersView(ttk.Frame):
    """Màn hình danh sách và phân quyền tài khoản người dùng."""

    def __init__(self, parent, auth_service: AuthService, session: AuthSession):
        super().__init__(parent, padding=16)
        self.auth_service = auth_service
        self.session = session

        HeaderBar(
            self,
            title="Quản lý Tài khoản & Phân quyền",
            subtitle="Danh sách nhân viên, quyền hạn hệ thống (Chỉ Quản trị viên)",
        )

        if not session.is_admin():
            ttk.Label(
                self,
                text="Bạn không có quyền truy cập màn hình này (Chỉ dành cho Admin).",
                foreground="#dc2626",
                font=("Segoe UI", 11, "bold"),
            ).pack(pady=20)
            return

        # Thanh công cụ
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 12))

        ttk.Button(
            toolbar,
            text="+ Thêm tài khoản",
            style="Primary.TButton",
            command=self._show_add_user_dialog,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Khóa / Mở khóa",
            command=self._toggle_user_status,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Đặt lại mật khẩu",
            command=self._reset_password,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Làm mới",
            command=self.load_data,
        ).pack(side="left")

        # Bảng danh sách
        columns = ("id", "username", "full_name", "role", "active", "created_at")
        headings = ("ID", "Tên đăng nhập", "Họ và tên", "Vai trò", "Trạng thái", "Ngày tạo")
        widths = (60, 140, 200, 120, 130, 160)

        self.table = DataTable(self, columns=columns, headings=headings, widths=widths)
        self.table.pack(fill="both", expand=True)

        self.load_data()

    def load_data(self) -> None:
        self.table.clear()
        try:
            users = self.auth_service.list_users(self.session)
            for u in users:
                role_text = "Quản trị viên (Admin)" if u["role"] == "admin" else "Nhân viên (Staff)"
                active_text = "Đang hoạt động" if u["active"] else "Đã khóa"
                created_text = u["created_at"][:10] if u.get("created_at") else ""
                self.table.insert_row(
                    (u["id"], u["username"], u["full_name"], role_text, active_text, created_text),
                    raw_data=u,
                )
        except Exception as e:
            show_error("Lỗi tải dữ liệu", str(e))

    def _show_add_user_dialog(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("Thêm tài khoản mới")
        dlg.geometry("400x340")
        dlg.transient(self)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Tên đăng nhập (viết liền):").pack(anchor="w", pady=(0, 2))
        ent_user = ttk.Entry(frame)
        ent_user.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Họ và tên đầy đủ:").pack(anchor="w", pady=(0, 2))
        ent_name = ttk.Entry(frame)
        ent_name.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Mật khẩu khởi tạo:").pack(anchor="w", pady=(0, 2))
        ent_pass = ttk.Entry(frame, show="•")
        ent_pass.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Vai trò:").pack(anchor="w", pady=(0, 2))
        cbo_role = ttk.Combobox(frame, values=["staff", "admin"], state="readonly")
        cbo_role.set("staff")
        cbo_role.pack(fill="x", pady=(0, 16))

        def save():
            u = ent_user.get().strip()
            n = ent_name.get().strip()
            p = ent_pass.get()
            r = cbo_role.get()
            try:
                self.auth_service.create_user(self.session, username=u, password=p, role=r, full_name=n)
                show_info("Thành công", f"Đã tạo tài khoản '{u}' thành công!")
                dlg.destroy()
                self.load_data()
            except Exception as e:
                show_error("Lỗi tạo tài khoản", str(e))

        ttk.Button(frame, text="Lưu tài khoản", style="Primary.TButton", command=save).pack(fill="x")

    def _toggle_user_status(self) -> None:
        selected = self.table.get_selected_data()
        if not selected:
            show_error("Thông báo", "Vui lòng chọn tài khoản từ bảng danh sách")
            return

        user_id = selected["id"]
        current_active = selected["active"]
        new_active = 0 if current_active == 1 else 1
        action_name = "khóa" if new_active == 0 else "mở khóa"

        if not show_confirm("Xác nhận", f"Bạn có chắc chắn muốn {action_name} tài khoản '{selected['username']}'?"):
            return

        try:
            self.auth_service.update_user(
                self.session,
                user_id=user_id,
                full_name=selected["full_name"],
                role=selected["role"],
                active=new_active,
            )
            show_info("Thành công", f"Đã {action_name} tài khoản thành công!")
            self.load_data()
        except Exception as e:
            show_error("Lỗi cập nhật", str(e))

    def _reset_password(self) -> None:
        selected = self.table.get_selected_data()
        if not selected:
            show_error("Thông báo", "Vui lòng chọn tài khoản từ bảng danh sách")
            return

        new_pass = simpledialog.askstring(
            "Đặt lại mật khẩu",
            f"Nhập mật khẩu mới cho tài khoản '{selected['username']}':",
            show="•",
            parent=self,
        )
        if not new_pass:
            return

        try:
            self.auth_service.reset_password(self.session, user_id=selected["id"], new_password=new_pass)
            show_info("Thành công", "Đã đặt lại mật khẩu thành công!")
        except Exception as e:
            show_error("Lỗi đặt lại mật khẩu", str(e))

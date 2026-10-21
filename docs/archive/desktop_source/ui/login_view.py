"""Màn hình đăng nhập tài khoản (LoginView)."""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from petcare.services.auth_service import AuthService, AuthSession
from petcare.ui.common import show_error
from petcare.ui.theme import COLOR_PRIMARY, COLOR_CARD


class LoginView(ttk.Frame):
    """Giao diện đăng nhập cho Admin và Nhân viên."""

    def __init__(
        self,
        parent,
        auth_service: AuthService,
        on_login_success: Callable[[AuthSession], None],
    ):
        super().__init__(parent, padding=32)
        self.auth_service = auth_service
        self.on_login_success = on_login_success

        # Khung thẻ chính ở giữa
        container = ttk.Frame(self, padding=32, style="Card.TFrame")
        container.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(
            container,
            text="PetCare Manager",
            font=("Segoe UI", 22, "bold"),
            foreground=COLOR_PRIMARY,
        ).pack(pady=(0, 4))

        ttk.Label(
            container,
            text="Hệ thống quản lý phòng khám & chăm sóc thú cưng",
            style="Muted.TLabel",
        ).pack(pady=(0, 24))

        # Form fields
        form = ttk.Frame(container)
        form.pack(fill="x", pady=8)

        ttk.Label(form, text="Tên đăng nhập:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 2))
        self.txt_username = ttk.Entry(form, width=32, font=("Segoe UI", 11))
        self.txt_username.pack(fill="x", pady=(0, 12))
        self.txt_username.focus()

        ttk.Label(form, text="Mật khẩu:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 2))
        self.txt_password = ttk.Entry(form, width=32, show="•", font=("Segoe UI", 11))
        self.txt_password.pack(fill="x", pady=(0, 20))
        self.txt_password.bind("<Return>", lambda e: self._handle_login())

        # Nút đăng nhập
        btn_login = ttk.Button(
            container,
            text="Đăng nhập",
            style="Primary.TButton",
            command=self._handle_login,
        )
        btn_login.pack(fill="x", pady=(0, 16))

        # Gợi ý tài khoản demo
        demo_box = ttk.LabelFrame(container, text="Tài khoản dùng thử (Demo)", padding=10)
        demo_box.pack(fill="x")
        ttk.Label(demo_box, text="• Admin: admin / Admin@123", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(demo_box, text="• Nhân viên: staff1 / Staff@123", style="Muted.TLabel").pack(anchor="w")

    def _handle_login(self) -> None:
        username = self.txt_username.get().strip()
        password = self.txt_password.get()

        if not username or not password:
            show_error("Lỗi đăng nhập", "Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu")
            return

        try:
            session = self.auth_service.login(username, password)
            self.on_login_success(session)
        except Exception as e:
            show_error("Đăng nhập thất bại", str(e))

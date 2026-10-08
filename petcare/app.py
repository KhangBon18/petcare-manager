"""Một Tk root, điều hướng bằng cách thay Frame nội dung."""

import tkinter as tk
from tkinter import ttk

from petcare.ui.common import PendingView


# Khi module thật hoàn thành, thay PendingView tại show_screen bằng Frame tương ứng.
SCREENS = {
    "login": ("Đăng nhập", "Khang", "Xác thực, PBKDF2 và phiên Admin/Nhân viên."),
    "users": ("Tài khoản", "Khang", "Quản lý tài khoản và kiểm tra quyền tại service."),
    "owners": ("Chủ nuôi", "Khang", "Quản lý thông tin chủ và kiểm tra dữ liệu nhập."),
    "pet_profile": ("Hồ sơ tổng hợp", "Khang", "Ghép thông tin thú cưng và lịch sử từ các module."),
    "pets": ("Thú cưng", "Quân", "Quản lý thú cưng, chủ, ngày sinh và trạng thái theo dõi."),
    "vaccinations": ("Tiêm phòng", "Quân", "Lưu hồ sơ tiêm, ngày nhắc và liên kết lượt dịch vụ."),
    "services": ("Danh mục dịch vụ", "Quý", "Quản lý dịch vụ, giá và quyền thay đổi danh mục."),
    "examinations": ("Khám bệnh", "Quý", "Lưu kết quả khám và lượt dịch vụ trong cùng giao dịch."),
    "appointments": ("Lịch hẹn", "Quý", "Quản lý lịch khám/chăm sóc; lịch hẹn chưa tạo khoản phí."),
    "visits": ("Lượt dịch vụ", "Nhàn", "Cung cấp API lượt dịch vụ chung cho khám, tiêm và chăm sóc."),
    "invoices": ("Hóa đơn", "Nhàn", "Lập, hủy và thanh toán trực tiếp; chống tính phí lặp."),
    "reports": ("Thống kê", "Quý, Quân, Nhàn", "Quý ghép báo cáo; Quân cung cấp query số lượng; Nhàn nhúng phần doanh thu."),
}


class PetCareApp:
    """Quản lý bố cục và Frame đang hiển thị; chưa có phiên đăng nhập."""

    def __init__(self, root):
        self.root = root
        self.current_view = None
        root.title("PetCare Manager — Bộ khung")
        root.geometry("960x680")
        root.minsize(800, 620)

        layout = ttk.Frame(root, padding=12)
        layout.pack(fill="both", expand=True)
        navigation = ttk.Frame(layout, padding=(0, 0, 16, 0))
        navigation.pack(side="left", fill="y")
        ttk.Label(navigation, text="PetCare Manager").pack(anchor="w", pady=(0, 12))
        for screen_id, (title, _, _) in SCREENS.items():
            ttk.Button(
                navigation,
                text=title,
                command=lambda key=screen_id: self.show_screen(key),
            ).pack(fill="x", pady=3)
        ttk.Button(navigation, text="Thoát", command=root.destroy).pack(
            fill="x", pady=(16, 0)
        )
        self.content = ttk.Frame(layout)
        self.content.pack(side="left", fill="both", expand=True)
        self.show_screen("login")

    def show_screen(self, screen_id):
        title, owner, task = SCREENS[screen_id]
        if self.current_view is not None:
            self.current_view.destroy()
        self.current_view = PendingView(self.content, title, owner, task)
        self.current_view.pack(fill="both", expand=True)


def run():
    """Tạo đúng một cửa sổ gốc và một vòng lặp sự kiện."""
    root = tk.Tk()
    PetCareApp(root)
    root.mainloop()

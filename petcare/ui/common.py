"""Frame thông báo dùng trong giai đoạn dựng bộ khung."""

from tkinter import ttk


class PendingView(ttk.Frame):
    """Hiển thị nhiệm vụ thật, không mô phỏng kết quả nghiệp vụ."""

    def __init__(self, parent, title, owner, task):
        super().__init__(parent, padding=24)
        ttk.Label(self, text=title, font=("", 18, "bold")).pack(anchor="w")
        ttk.Label(self, text="Chưa triển khai", foreground="#9a3412").pack(
            anchor="w", pady=(16, 8)
        )
        ttk.Label(self, text=f"Phụ trách: {owner}").pack(anchor="w")
        ttk.Label(self, text=task, wraplength=560, justify="left").pack(
            anchor="w", pady=12
        )
        ttk.Label(
            self,
            text="Bộ khung chưa xác thực tài khoản, lưu dữ liệu hoặc thanh toán.\n"
            "Các nút bên trái chỉ dùng để xem màn hình dự kiến.",
            wraplength=560,
            justify="left",
        ).pack(anchor="w", pady=12)

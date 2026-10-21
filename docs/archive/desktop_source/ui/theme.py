"""Hệ thống màu sắc, kiểu dáng (Theme) và định dạng giao diện."""

import tkinter as tk
from tkinter import ttk

# Bảng màu chuẩn giao diện PetCare Manager
COLOR_BG = "#f8fafc"          # Nền chính nhẹ nhàng
COLOR_CARD = "#ffffff"        # Nền card/bảng
COLOR_PRIMARY = "#2563eb"     # Xanh chủ đạo
COLOR_PRIMARY_HOVER = "#1d4ed8"
COLOR_SECONDARY = "#0d9488"   # Xanh ngọc
COLOR_TEXT = "#0f172a"        # Màu chữ chính
COLOR_MUTED = "#64748b"       # Màu chữ phụ
COLOR_BORDER = "#cbd5e1"      # Viền
COLOR_SUCCESS = "#16a34a"     # Thành công
COLOR_DANGER = "#dc2626"      # Cảnh báo/Xóa
COLOR_WARNING = "#d97706"     # Chờ/Nhắc nhở


def format_vnd(amount: int | float | None) -> str:
    """Định dạng số nguyên sang chuỗi tiền tệ VND chuẩn Việt Nam."""
    if amount is None:
        return "0 đ"
    try:
        val = int(amount)
        return f"{val:,.0f} đ".replace(",", ".")
    except (ValueError, TypeError):
        return "0 đ"


def apply_theme(root: tk.Tk) -> None:
    """Cấu hình ttk Style cho toàn bộ ứng dụng."""
    style = ttk.Style(root)
    # Thử sử dụng theme 'clam' nếu có để hỗ trợ tùy biến màu sắc tốt nhất
    available_themes = style.theme_names()
    if "clam" in available_themes:
        style.theme_use("clam")

    # Cấu hình chung
    style.configure(".", background=COLOR_BG, foreground=COLOR_TEXT, font=("Segoe UI", 10))
    style.configure("TFrame", background=COLOR_BG)
    style.configure("Card.TFrame", background=COLOR_CARD, relief="flat")

    # Label
    style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT)
    style.configure("Card.TLabel", background=COLOR_CARD, foreground=COLOR_TEXT)
    style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground=COLOR_TEXT)
    style.configure("SubHeader.TLabel", font=("Segoe UI", 11, "bold"), foreground=COLOR_TEXT)
    style.configure("Muted.TLabel", font=("Segoe UI", 9), foreground=COLOR_MUTED)
    style.configure("StatValue.TLabel", font=("Segoe UI", 16, "bold"), foreground=COLOR_PRIMARY)

    # Button
    style.configure(
        "TButton",
        padding=(12, 6),
        font=("Segoe UI", 10),
        borderwidth=1,
    )
    style.configure(
        "Primary.TButton",
        background=COLOR_PRIMARY,
        foreground="#ffffff",
        font=("Segoe UI", 10, "bold"),
    )
    style.map(
        "Primary.TButton",
        background=[("active", COLOR_PRIMARY_HOVER), ("pressed", "#1e40af")],
        foreground=[("active", "#ffffff")],
    )

    style.configure(
        "Success.TButton",
        background=COLOR_SUCCESS,
        foreground="#ffffff",
        font=("Segoe UI", 10, "bold"),
    )
    style.map("Success.TButton", background=[("active", "#15803d")])

    style.configure(
        "Danger.TButton",
        background=COLOR_DANGER,
        foreground="#ffffff",
        font=("Segoe UI", 10),
    )
    style.map("Danger.TButton", background=[("active", "#b91c1c")])

    # Treeview (Bảng danh sách)
    style.configure(
        "Treeview",
        background=COLOR_CARD,
        foreground=COLOR_TEXT,
        rowheight=28,
        fieldbackground=COLOR_CARD,
        bordercolor=COLOR_BORDER,
    )
    style.configure(
        "Treeview.Heading",
        background="#e2e8f0",
        foreground=COLOR_TEXT,
        font=("Segoe UI", 10, "bold"),
        padding=(6, 6),
    )
    style.map("Treeview", background=[("selected", "#bfdbfe")], foreground=[("selected", COLOR_TEXT)])

"""Các widget dùng chung, thông báo và bảng hiển thị dữ liệu."""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from petcare.ui.theme import COLOR_CARD, COLOR_BORDER, COLOR_PRIMARY, format_vnd


class PendingView(ttk.Frame):
    """Giữ tương thích ngược cho các màn hình đang hoàn thiện."""

    def __init__(self, parent, title: str, owner: str, task: str):
        super().__init__(parent, padding=24)
        ttk.Label(self, text=title, font=("", 18, "bold")).pack(anchor="w")
        ttk.Label(self, text="Chưa triển khai", foreground="#9a3412").pack(
            anchor="w", pady=(16, 8)
        )
        ttk.Label(self, text=f"Phụ trách: {owner}").pack(anchor="w")
        ttk.Label(self, text=task, wraplength=560, justify="left").pack(
            anchor="w", pady=12
        )


class HeaderBar(ttk.Frame):
    """Thanh tiêu đề của từng trang màn hình."""

    def __init__(self, parent, title: str, subtitle: str = ""):
        super().__init__(parent, padding=(0, 0, 0, 16))
        self.pack(fill="x")
        ttk.Label(self, text=title, style="Header.TLabel").pack(anchor="w")
        if subtitle:
            ttk.Label(self, text=subtitle, style="Muted.TLabel").pack(anchor="w", pady=(2, 0))


class StatCard(ttk.Frame):
    """Thẻ hiển thị chỉ số thống kê."""

    def __init__(self, parent, title: str, value_text: str, subtitle: str = ""):
        super().__init__(parent, padding=14, style="Card.TFrame")
        ttk.Label(self, text=title, style="Muted.TLabel").pack(anchor="w")
        self.lbl_value = ttk.Label(self, text=value_text, style="StatValue.TLabel")
        self.lbl_value.pack(anchor="w", pady=(4, 2))
        if subtitle:
            ttk.Label(self, text=subtitle, style="Muted.TLabel").pack(anchor="w")

    def set_value(self, new_val: str) -> None:
        self.lbl_value.config(text=new_val)


class DataTable(ttk.Frame):
    """Bảng dữ liệu Treeview có thanh cuộn ngang, dọc và các helper thao tác."""

    def __init__(
        self,
        parent,
        columns: tuple[str, ...],
        headings: tuple[str, ...],
        widths: tuple[int, ...] | None = None,
        on_select: Callable[[dict[str, Any]], None] | None = None,
        on_double_click: Callable[[dict[str, Any]], None] | None = None,
    ):
        super().__init__(parent)
        self.columns = columns
        self.on_select = on_select
        self.on_double_click = on_double_click
        self.row_data_map: dict[str, dict[str, Any]] = {}

        # Cấu hình thanh cuộn
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Cấu hình tiêu đề và độ rộng cột
        for idx, col in enumerate(columns):
            heading_text = headings[idx] if idx < len(headings) else col
            self.tree.heading(col, text=heading_text, anchor="w")
            width = widths[idx] if widths and idx < len(widths) else 120
            self.tree.column(col, width=width, anchor="w", stretch=True)

        if on_select:
            self.tree.bind("<<TreeviewSelect>>", self._handle_select)
        if on_double_click:
            self.tree.bind("<Double-1>", self._handle_double_click)

    def _handle_select(self, event=None):
        selected = self.get_selected_data()
        if selected and self.on_select:
            self.on_select(selected)

    def _handle_double_click(self, event=None):
        selected = self.get_selected_data()
        if selected and self.on_double_click:
            self.on_double_click(selected)

    def clear(self) -> None:
        """Xóa toàn bộ các dòng hiện có."""
        self.tree.delete(*self.tree.get_children())
        self.row_data_map.clear()

    def insert_row(self, values: tuple[Any, ...], raw_data: dict[str, Any] | None = None) -> str:
        """Thêm một dòng vào bảng, kèm theo dữ liệu nguyên bản raw_data."""
        item_id = self.tree.insert("", "end", values=values)
        if raw_data is not None:
            self.row_data_map[item_id] = raw_data
        return item_id

    def get_selected_data(self) -> dict[str, Any] | None:
        """Lấy dữ liệu nguyên bản của dòng đang được chọn."""
        sel = self.tree.selection()
        if not sel:
            return None
        return self.row_data_map.get(sel[0])

    def get_selected_values(self) -> tuple[Any, ...] | None:
        """Lấy giá trị text của các cột dòng đang chọn."""
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0], "values")


def show_error(title: str, message: str) -> None:
    messagebox.showerror(title, message)


def show_info(title: str, message: str) -> None:
    messagebox.showinfo(title, message)


def show_confirm(title: str, message: str) -> bool:
    return messagebox.askyesno(title, message)

"""Màn hình doanh thu và dịch vụ phổ biến (RevenueView). Nhúng vào ReportsView."""

from tkinter import ttk
from typing import Any

from petcare.ui.common import DataTable
from petcare.ui.theme import format_vnd


class RevenueView(ttk.Frame):
    """Bảng chi tiết doanh thu và danh sách dịch vụ đóng góp doanh thu cao nhất."""

    def __init__(self, parent):
        super().__init__(parent)

        ttk.Label(
            self,
            text="Top Dịch vụ Đóng góp Doanh thu Cao nhất:",
            style="SubHeader.TLabel",
        ).pack(anchor="w", pady=(4, 6))

        columns = ("rank", "service_name", "usage_count", "total_amount")
        headings = ("Xếp hạng", "Tên dịch vụ", "Số lượt sử dụng", "Tổng doanh thu (VND)")
        widths = (70, 260, 140, 160)

        self.table = DataTable(self, columns=columns, headings=headings, widths=widths)
        self.table.pack(fill="both", expand=True)

    def update_data(self, popular_services: list[dict[str, Any]]) -> None:
        self.table.clear()
        for idx, item in enumerate(popular_services, start=1):
            self.table.insert_row(
                (
                    f"#{idx}",
                    item["service_name"],
                    item["usage_count"],
                    format_vnd(item["total_revenue"]),
                )
            )

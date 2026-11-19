"""Màn hình thống kê báo cáo (ReportsView) - Nhúng RevenueView."""

from datetime import date
import tkinter as tk
from tkinter import ttk

from petcare.services.auth_service import AuthSession
from petcare.services.report_service import ReportService
from petcare.ui.common import DataTable, HeaderBar, StatCard, show_error
from petcare.ui.revenue_view import RevenueView
from petcare.ui.theme import format_vnd


class ReportsView(ttk.Frame):
    """Bảng điều khiển thống kê tổng hợp số liệu hoạt động và doanh thu theo kỳ."""

    def __init__(self, parent, report_service: ReportService, session: AuthSession):
        super().__init__(parent, padding=16)
        self.report_service = report_service
        self.session = session

        HeaderBar(
            self,
            title="Báo cáo & Thống kê Hoạt động",
            subtitle="Tổng hợp doanh thu, lượt khám, tiêm chủng, cơ cấu loài và dịch vụ phổ biến",
        )

        # Thanh lọc khoảng ngày
        filter_bar = ttk.Frame(self)
        filter_bar.pack(fill="x", pady=(0, 16))

        today = date.today()
        first_day_of_month = today.replace(day=1)

        ttk.Label(filter_bar, text="Từ ngày (YYYY-MM-DD):").pack(side="left", padx=(0, 4))
        self.ent_start = ttk.Entry(filter_bar, width=12)
        self.ent_start.insert(0, first_day_of_month.isoformat())
        self.ent_start.pack(side="left", padx=(0, 10))

        ttk.Label(filter_bar, text="Đến ngày (YYYY-MM-DD):").pack(side="left", padx=(0, 4))
        self.ent_end = ttk.Entry(filter_bar, width=12)
        self.ent_end.insert(0, today.isoformat())
        self.ent_end.pack(side="left", padx=(0, 12))

        ttk.Button(filter_bar, text="Xem báo cáo", style="Primary.TButton", command=self.load_data).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(filter_bar, text="Hôm nay", command=self._set_today).pack(side="left", padx=(0, 6))
        ttk.Button(filter_bar, text="Tháng này", command=self._set_this_month).pack(side="left")

        # 4 Thẻ chỉ số tổng quan (StatCards)
        cards_frame = ttk.Frame(self)
        cards_frame.pack(fill="x", pady=(0, 16))

        self.card_rev = StatCard(cards_frame, title="Doanh thu thực thu", value_text="0 đ", subtitle="Các hóa đơn đã thanh toán")
        self.card_rev.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.card_invoices = StatCard(cards_frame, title="Hóa đơn thanh toán", value_text="0", subtitle="Số đơn đã hoàn tất")
        self.card_invoices.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.card_exams = StatCard(cards_frame, title="Lượt khám bệnh", value_text="0", subtitle="Hồ sơ bệnh án tạo mới")
        self.card_exams.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.card_vaccines = StatCard(cards_frame, title="Thú cưng tiêm phòng", value_text="0", subtitle="Số lượng thú cưng duy nhất")
        self.card_vaccines.pack(side="left", fill="both", expand=True, padx=(0, 0))

        # Khung chia 2 cột: Cột trái Cơ cấu Loài - Cột phải RevenueView
        details_frame = ttk.Frame(self)
        details_frame.pack(fill="both", expand=True)

        # Cột trái: Phân bố Loài
        left_col = ttk.Frame(details_frame)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 12))

        ttk.Label(left_col, text="Phân bố Thú cưng theo Loài:", style="SubHeader.TLabel").pack(anchor="w", pady=(4, 6))
        self.table_species = DataTable(
            left_col,
            columns=("species", "count", "ratio"),
            headings=("Loài", "Số lượng", "Tỷ lệ (%)"),
            widths=(110, 80, 80),
        )
        self.table_species.pack(fill="both", expand=True)

        # Cột phải: RevenueView (Top Dịch vụ phổ biến)
        right_col = ttk.Frame(details_frame)
        right_col.pack(side="right", fill="both", expand=True)

        self.revenue_view = RevenueView(right_col)
        self.revenue_view.pack(fill="both", expand=True)

        self.load_data()

    def _set_today(self) -> None:
        today_str = date.today().isoformat()
        self.ent_start.delete(0, "end")
        self.ent_start.insert(0, today_str)
        self.ent_end.delete(0, "end")
        self.ent_end.insert(0, today_str)
        self.load_data()

    def _set_this_month(self) -> None:
        today = date.today()
        first_day = today.replace(day=1)
        self.ent_start.delete(0, "end")
        self.ent_start.insert(0, first_day.isoformat())
        self.ent_end.delete(0, "end")
        self.ent_end.insert(0, today.isoformat())
        self.load_data()

    def load_data(self) -> None:
        start_date = self.ent_start.get().strip()
        end_date = self.ent_end.get().strip()

        try:
            summary = self.report_service.get_summary(self.session, start_date=start_date, end_date=end_date)

            # Cập nhật các thẻ chỉ số
            self.card_rev.set_value(format_vnd(summary["total_revenue_vnd"]))
            self.card_invoices.set_value(str(summary["paid_invoices_count"]))
            self.card_exams.set_value(str(summary["exam_count"]))
            self.card_vaccines.set_value(str(summary["vaccinated_pets_count"]))

            # Cập nhật bảng loài
            self.table_species.clear()
            species_list = summary["species_distribution"]
            total_pets = sum(s["count"] for s in species_list)
            for s in species_list:
                ratio_str = f"{(s['count'] / total_pets * 100):.1f}%" if total_pets > 0 else "0%"
                self.table_species.insert_row((s["species"], s["count"], ratio_str))

            # Cập nhật revenue_view (Dịch vụ phổ biến)
            self.revenue_view.update_data(summary["popular_services"])

        except Exception as e:
            show_error("Lỗi tải báo cáo", str(e))

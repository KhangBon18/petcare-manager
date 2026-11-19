"""Màn hình lượt sử dụng dịch vụ (VisitsView)."""

from datetime import date
import tkinter as tk
from tkinter import ttk

from petcare.services.auth_service import AuthSession
from petcare.services.catalog_service import CatalogService
from petcare.services.pet_service import PetService
from petcare.services.visit_service import VisitService
from petcare.ui.common import DataTable, HeaderBar, show_error, show_info
from petcare.ui.theme import format_vnd


class VisitsView(ttk.Frame):
    """Giao diện xem toàn bộ các lượt dịch vụ đã thực hiện và trạng thái lập hóa đơn."""

    def __init__(
        self,
        parent,
        visit_service: VisitService,
        pet_service: PetService,
        catalog_service: CatalogService,
        session: AuthSession,
    ):
        super().__init__(parent, padding=16)
        self.visit_service = visit_service
        self.pet_service = pet_service
        self.catalog_service = catalog_service
        self.session = session

        HeaderBar(
            self,
            title="Lượt Sử dụng Dịch vụ",
            subtitle="Danh sách các lượt khám, tiêm, tắm spa, xét nghiệm và đối soát thanh toán",
        )

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 12))

        ttk.Button(
            toolbar,
            text="+ Ghi nhận dịch vụ Chăm sóc / Spa",
            style="Primary.TButton",
            command=self._show_record_usage_dialog,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Làm mới",
            command=self.load_data,
        ).pack(side="left")

        # Bảng danh sách các lượt dịch vụ
        columns = ("id", "date", "pet_name", "owner_name", "service_name", "category", "price", "billing_status")
        headings = ("ID", "Ngày thực hiện", "Thú cưng", "Chủ nuôi", "Tên dịch vụ", "Phân loại", "Đơn giá (VND)", "Hóa đơn")
        widths = (40, 100, 110, 130, 180, 110, 110, 130)

        self.table = DataTable(self, columns=columns, headings=headings, widths=widths)
        self.table.pack(fill="both", expand=True)

        self.load_data()

    def load_data(self) -> None:
        self.table.clear()
        try:
            visits = self.visit_service.list_all_visits(self.session)
            for v in visits:
                if not v["is_billed"]:
                    bill_text = "Chưa tính tiền"
                else:
                    st = v.get("invoice_status")
                    if st == "paid":
                        bill_text = "Đã thanh toán"
                    elif st == "unpaid":
                        bill_text = "Đã lập (Chưa trả)"
                    elif st == "cancelled":
                        bill_text = "Đã hủy"
                    else:
                        bill_text = "Đã lập hóa đơn"

                self.table.insert_row(
                    (
                        v["id"],
                        v["performed_at"][:10],
                        v["pet_name"],
                        v["owner_name"],
                        v["service_name"],
                        v["service_category"],
                        format_vnd(v["unit_price_vnd"]),
                        bill_text,
                    ),
                    raw_data=v,
                )
        except Exception as e:
            show_error("Lỗi tải dữ liệu", str(e))

    def _show_record_usage_dialog(self) -> None:
        try:
            pets = self.pet_service.list_pets(self.session, active_only=True)
            if not pets:
                show_error("Chưa có thú cưng", "Vui lòng thêm thú cưng trước khi ghi nhận dịch vụ")
                return

            services = self.catalog_service.list_services(self.session, active_only=True)
            care_services = [s for s in services if s["category"] in ("Chăm sóc", "Xét nghiệm", "Khác")]
            if not care_services:
                care_services = services
        except Exception as e:
            show_error("Lỗi", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title("Ghi nhận lượt dịch vụ chăm sóc / spa / xét nghiệm")
        dlg.geometry("480x420")
        dlg.transient(self)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=20)
        frame.pack(fill="both", expand=True)

        # Chọn thú cưng
        ttk.Label(frame, text="Thú cưng thực hiện dịch vụ:").pack(anchor="w", pady=(0, 2))
        pet_options = [f"{p['id']}: {p['name']} ({p['species']} - Chủ: {p['owner_name']})" for p in pets]
        cbo_pet = ttk.Combobox(frame, values=pet_options, state="readonly")
        cbo_pet.current(0)
        cbo_pet.pack(fill="x", pady=(0, 10))

        # Chọn dịch vụ
        ttk.Label(frame, text="Dịch vụ:").pack(anchor="w", pady=(0, 2))
        svc_options = [f"{s['id']}: {s['name']} - {format_vnd(s['price_vnd'])}" for s in care_services]
        cbo_svc = ttk.Combobox(frame, values=svc_options, state="readonly")
        cbo_svc.current(0)
        cbo_svc.pack(fill="x", pady=(0, 10))

        # Ngày thực hiện
        ttk.Label(frame, text="Ngày thực hiện (YYYY-MM-DD):").pack(anchor="w", pady=(0, 2))
        ent_date = ttk.Entry(frame)
        ent_date.insert(0, date.today().isoformat())
        ent_date.pack(fill="x", pady=(0, 10))

        # Ghi chú
        ttk.Label(frame, text="Ghi chú thêm:").pack(anchor="w", pady=(0, 2))
        ent_notes = ttk.Entry(frame)
        ent_notes.pack(fill="x", pady=(0, 16))

        def save():
            p_val = cbo_pet.get()
            s_val = cbo_svc.get()
            if not p_val or not s_val:
                show_error("Lỗi", "Vui lòng chọn thú cưng và dịch vụ")
                return

            pet_id = int(p_val.split(":")[0])
            svc_id = int(s_val.split(":")[0])

            try:
                self.visit_service.record_service_usage(
                    self.session,
                    pet_id=pet_id,
                    service_id=svc_id,
                    performed_at=ent_date.get().strip(),
                    notes=ent_notes.get().strip(),
                )
                show_info("Thành công", "Đã ghi nhận lượt dịch vụ thành công!")
                dlg.destroy()
                self.load_data()
            except Exception as e:
                show_error("Lỗi", str(e))

        ttk.Button(frame, text="Lưu lượt dịch vụ", style="Primary.TButton", command=save).pack(fill="x", pady=(8, 0))

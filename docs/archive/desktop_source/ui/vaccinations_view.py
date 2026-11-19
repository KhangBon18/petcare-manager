"""Màn hình hồ sơ tiêm phòng và lịch nhắc vaccine (VaccinationsView)."""

from datetime import date, timedelta
import tkinter as tk
from tkinter import ttk

from petcare.services.auth_service import AuthSession
from petcare.services.catalog_service import CatalogService
from petcare.services.pet_service import PetService
from petcare.services.vaccination_service import VaccinationService
from petcare.ui.common import DataTable, HeaderBar, show_confirm, show_error, show_info
from petcare.ui.theme import format_vnd


class VaccinationsView(ttk.Frame):
    """Giao diện quản lý tiêm phòng, lịch nhắc hẹn và tạo lượt dịch vụ tiêm."""

    def __init__(
        self,
        parent,
        vaccination_service: VaccinationService,
        pet_service: PetService,
        catalog_service: CatalogService,
        session: AuthSession,
    ):
        super().__init__(parent, padding=16)
        self.vaccination_service = vaccination_service
        self.pet_service = pet_service
        self.catalog_service = catalog_service
        self.session = session

        HeaderBar(
            self,
            title="Quản lý Tiêm phòng & Lịch nhắc",
            subtitle="Theo dõi các mũi tiêm phòng, ngày hẹn nhắc lại và tạo lượt dịch vụ tiêm",
        )

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 12))

        ttk.Button(
            toolbar,
            text="+ Ghi nhận mũi tiêm mới",
            style="Primary.TButton",
            command=self._show_record_vaccination_dialog,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Đánh dấu đã xử lý nhắc",
            command=self._resolve_selected_reminder,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Làm mới",
            command=self.load_data,
        ).pack(side="left")

        # Khung nhắc hẹn sắp tới
        reminder_box = ttk.LabelFrame(self, text="⚠️ Lịch nhắc tiêm phòng đến hạn (Trong vòng 30 ngày)", padding=10)
        reminder_box.pack(fill="x", pady=(0, 14))

        self.table_reminders = DataTable(
            reminder_box,
            columns=("id", "pet_name", "owner_name", "owner_phone", "vaccine", "next_due"),
            headings=("ID", "Thú cưng", "Chủ nuôi", "Số điện thoại", "Vaccine cần nhắc", "Hạn tiêm"),
            widths=(40, 120, 140, 120, 180, 100),
        )
        self.table_reminders.pack(fill="x")

        # Bảng toàn bộ lịch sử tiêm phòng
        ttk.Label(self, text="Toàn bộ lịch sử tiêm phòng:", style="SubHeader.TLabel").pack(anchor="w", pady=(6, 4))
        columns = ("id", "date", "pet_name", "owner_name", "vaccine", "service", "next_due", "reminder_status", "price")
        headings = ("ID", "Ngày tiêm", "Thú cưng", "Chủ nuôi", "Tên vaccine", "Dịch vụ", "Hẹn tiêm lại", "Trạng thái nhắc", "Chi phí")
        widths = (40, 95, 110, 130, 150, 140, 100, 120, 100)

        self.table_all = DataTable(self, columns=columns, headings=headings, widths=widths)
        self.table_all.pack(fill="both", expand=True)

        self.load_data()

    def load_data(self) -> None:
        # Tải danh sách nhắc nhở
        self.table_reminders.clear()
        try:
            reminders = self.vaccination_service.get_upcoming_reminders(self.session, days_ahead=30)
            for r in reminders:
                self.table_reminders.insert_row(
                    (r["id"], r["pet_name"], r["owner_name"], r["owner_phone"], r["vaccine_name"], r["next_due_date"]),
                    raw_data=r,
                )
        except Exception as e:
            show_error("Lỗi", str(e))

        # Tải danh sách tất cả mũi tiêm
        self.table_all.clear()
        try:
            vaccinations = self.vaccination_service.list_vaccinations(self.session)
            for v in vaccinations:
                rem_text = "Đã hoàn thành" if v["reminder_resolved"] else ("Chờ nhắc" if v["next_due_date"] else "-")
                self.table_all.insert_row(
                    (
                        v["id"],
                        v["injection_date"],
                        v["pet_name"],
                        v["owner_name"],
                        v["vaccine_name"],
                        v["service_name"],
                        v["next_due_date"] or "-",
                        rem_text,
                        format_vnd(v["unit_price_vnd"]),
                    ),
                    raw_data=v,
                )
        except Exception as e:
            show_error("Lỗi", str(e))

    def _show_record_vaccination_dialog(self) -> None:
        try:
            pets = self.pet_service.list_pets(self.session, active_only=True)
            if not pets:
                show_error("Chưa có thú cưng", "Vui lòng thêm thú cưng trước khi tạo mũi tiêm")
                return

            services = self.catalog_service.list_services(self.session, active_only=True)
            vac_services = [s for s in services if s["category"] == "Tiêm phòng"]
            if not vac_services:
                vac_services = services
        except Exception as e:
            show_error("Lỗi", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title("Ghi nhận mũi tiêm phòng mới")
        dlg.geometry("500x500")
        dlg.transient(self)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=20)
        frame.pack(fill="both", expand=True)

        # Chọn thú cưng
        ttk.Label(frame, text="Thú cưng:").pack(anchor="w", pady=(0, 2))
        pet_options = [f"{p['id']}: {p['name']} ({p['species']} - Chủ: {p['owner_name']})" for p in pets]
        cbo_pet = ttk.Combobox(frame, values=pet_options, state="readonly")
        cbo_pet.current(0)
        cbo_pet.pack(fill="x", pady=(0, 10))

        # Chọn gói dịch vụ
        ttk.Label(frame, text="Gói dịch vụ tiêm:").pack(anchor="w", pady=(0, 2))
        svc_options = [f"{s['id']}: {s['name']} - {format_vnd(s['price_vnd'])}" for s in vac_services]
        cbo_svc = ttk.Combobox(frame, values=svc_options, state="readonly")
        cbo_svc.current(0)
        cbo_svc.pack(fill="x", pady=(0, 10))

        # Tên vaccine
        ttk.Label(frame, text="Tên vaccine cụ thể (ví dụ: Rabisin, Nobivac 7,...):").pack(anchor="w", pady=(0, 2))
        ent_vac_name = ttk.Entry(frame)
        ent_vac_name.pack(fill="x", pady=(0, 10))

        # Ngày tiêm
        today_str = date.today().isoformat()
        ttk.Label(frame, text="Ngày tiêm (YYYY-MM-DD):").pack(anchor="w", pady=(0, 2))
        ent_date = ttk.Entry(frame)
        ent_date.insert(0, today_str)
        ent_date.pack(fill="x", pady=(0, 10))

        # Ngày hẹn tiêm nhắc lại
        suggested_next_due = (date.today() + timedelta(days=365)).isoformat()
        ttk.Label(frame, text="Ngày hẹn tiêm nhắc lại (YYYY-MM-DD, tùy chọn):").pack(anchor="w", pady=(0, 2))
        ent_next_due = ttk.Entry(frame)
        ent_next_due.insert(0, suggested_next_due)
        ent_next_due.pack(fill="x", pady=(0, 16))

        def save():
            p_val = cbo_pet.get()
            s_val = cbo_svc.get()
            if not p_val or not s_val:
                show_error("Lỗi", "Vui lòng chọn đầy đủ thú cưng và gói dịch vụ")
                return

            pet_id = int(p_val.split(":")[0])
            svc_id = int(s_val.split(":")[0])

            try:
                self.vaccination_service.record_vaccination(
                    self.session,
                    {
                        "pet_id": pet_id,
                        "service_id": svc_id,
                        "vaccine_name": ent_vac_name.get().strip(),
                        "injection_date": ent_date.get().strip(),
                        "next_due_date": ent_next_due.get().strip() or None,
                    },
                )
                show_info("Thành công", "Đã lưu mũi tiêm và tạo lượt dịch vụ tương ứng thành công!")
                dlg.destroy()
                self.load_data()
            except Exception as e:
                show_error("Lỗi ghi nhận", str(e))

        ttk.Button(frame, text="Lưu hồ sơ tiêm phòng", style="Primary.TButton", command=save).pack(fill="x", pady=(8, 0))

    def _resolve_selected_reminder(self) -> None:
        selected = self.table_reminders.get_selected_data()
        if not selected:
            # Nếu không chọn ở bảng trên, thử kiểm tra ở bảng dưới
            selected = self.table_all.get_selected_data()
            if not selected:
                show_error("Thông báo", "Vui lòng chọn một dòng nhắc nhở để đánh dấu đã xử lý")
                return

        vac_id = selected["id"]
        if not show_confirm("Xác nhận", f"Đánh dấu đã hoàn thành nhắc nhở cho mũi tiêm #{vac_id} ({selected['vaccine_name']})?"):
            return

        try:
            self.vaccination_service.resolve_reminder(self.session, vac_id)
            show_info("Thành công", "Đã cập nhật trạng thái nhắc nhở!")
            self.load_data()
        except Exception as e:
            show_error("Lỗi", str(e))

"""Màn hình hồ sơ khám bệnh (ExaminationsView)."""

from datetime import date
import tkinter as tk
from tkinter import ttk

from petcare.services.auth_service import AuthSession
from petcare.services.catalog_service import CatalogService
from petcare.services.exam_service import ExamService
from petcare.services.pet_service import PetService
from petcare.ui.common import DataTable, HeaderBar, show_error, show_info
from petcare.ui.theme import format_vnd


class ExaminationsView(ttk.Frame):
    """Giao diện quản lý hồ sơ khám bệnh và tạo ca khám kèm lượt dịch vụ."""

    def __init__(
        self,
        parent,
        exam_service: ExamService,
        pet_service: PetService,
        catalog_service: CatalogService,
        session: AuthSession,
    ):
        super().__init__(parent, padding=16)
        self.exam_service = exam_service
        self.pet_service = pet_service
        self.catalog_service = catalog_service
        self.session = session

        HeaderBar(
            self,
            title="Quản lý Khám bệnh",
            subtitle="Ghi nhận triệu chứng, chẩn đoán, đơn thuốc và tự động liên kết chi phí dịch vụ",
        )

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 12))

        ttk.Button(
            toolbar,
            text="+ Ghi nhận ca khám mới",
            style="Primary.TButton",
            command=self._show_record_exam_dialog,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Làm mới",
            command=self.load_data,
        ).pack(side="left")

        # Bảng danh sách ca khám
        columns = ("id", "date", "pet_name", "owner_name", "service", "symptoms", "diagnosis", "medicines", "price")
        headings = ("ID", "Ngày khám", "Thú cưng", "Chủ nuôi", "Gói dịch vụ", "Triệu chứng", "Chẩn đoán", "Đơn thuốc", "Chi phí")
        widths = (40, 95, 110, 130, 140, 150, 150, 140, 100)

        self.table = DataTable(self, columns=columns, headings=headings, widths=widths)
        self.table.pack(fill="both", expand=True)

        self.load_data()

    def load_data(self) -> None:
        self.table.clear()
        try:
            exams = self.exam_service.list_exams(self.session)
            for ex in exams:
                self.table.insert_row(
                    (
                        ex["id"],
                        ex["exam_date"],
                        ex["pet_name"],
                        ex["owner_name"],
                        ex["service_name"],
                        ex["symptoms"],
                        ex["diagnosis"],
                        ex["medicines"] or "Không có",
                        format_vnd(ex["unit_price_vnd"]),
                    ),
                    raw_data=ex,
                )
        except Exception as e:
            show_error("Lỗi tải dữ liệu", str(e))

    def _show_record_exam_dialog(self) -> None:
        try:
            pets = self.pet_service.list_pets(self.session, active_only=True)
            if not pets:
                show_error("Chưa có thú cưng", "Vui lòng thêm thú cưng trước khi tạo ca khám")
                return

            services = self.catalog_service.list_services(self.session, active_only=True)
            exam_services = [s for s in services if s["category"] == "Khám bệnh"]
            if not exam_services:
                exam_services = services
        except Exception as e:
            show_error("Lỗi", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title("Ghi nhận ca khám bệnh mới")
        dlg.geometry("500x520")
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

        # Chọn dịch vụ
        ttk.Label(frame, text="Gói dịch vụ khám:").pack(anchor="w", pady=(0, 2))
        svc_options = [f"{s['id']}: {s['name']} - {format_vnd(s['price_vnd'])}" for s in exam_services]
        cbo_svc = ttk.Combobox(frame, values=svc_options, state="readonly")
        cbo_svc.current(0)
        cbo_svc.pack(fill="x", pady=(0, 10))

        # Ngày khám
        ttk.Label(frame, text="Ngày khám (YYYY-MM-DD):").pack(anchor="w", pady=(0, 2))
        ent_date = ttk.Entry(frame)
        ent_date.insert(0, date.today().isoformat())
        ent_date.pack(fill="x", pady=(0, 10))

        # Triệu chứng
        ttk.Label(frame, text="Triệu chứng ban đầu:").pack(anchor="w", pady=(0, 2))
        ent_symptoms = ttk.Entry(frame)
        ent_symptoms.pack(fill="x", pady=(0, 10))

        # Chẩn đoán
        ttk.Label(frame, text="Chẩn đoán của bác sĩ:").pack(anchor="w", pady=(0, 2))
        ent_diag = ttk.Entry(frame)
        ent_diag.pack(fill="x", pady=(0, 10))

        # Đơn thuốc
        ttk.Label(frame, text="Đơn thuốc / Hướng dẫn điều trị:").pack(anchor="w", pady=(0, 2))
        ent_meds = ttk.Entry(frame)
        ent_meds.pack(fill="x", pady=(0, 16))

        def save():
            p_val = cbo_pet.get()
            s_val = cbo_svc.get()
            if not p_val or not s_val:
                show_error("Lỗi", "Vui lòng chọn đầy đủ thú cưng và gói dịch vụ")
                return

            pet_id = int(p_val.split(":")[0])
            svc_id = int(s_val.split(":")[0])

            try:
                self.exam_service.record_exam(
                    self.session,
                    {
                        "pet_id": pet_id,
                        "service_id": svc_id,
                        "exam_date": ent_date.get().strip(),
                        "symptoms": ent_symptoms.get().strip(),
                        "diagnosis": ent_diag.get().strip(),
                        "medicines": ent_meds.get().strip(),
                    },
                )
                show_info("Thành công", "Đã lưu ca khám và tạo lượt dịch vụ tương ứng thành công!")
                dlg.destroy()
                self.load_data()
            except Exception as e:
                show_error("Lỗi ghi nhận", str(e))

        ttk.Button(frame, text="Lưu hồ sơ khám bệnh", style="Primary.TButton", command=save).pack(fill="x", pady=(8, 0))

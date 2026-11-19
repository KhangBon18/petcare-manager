"""Màn hình hồ sơ tổng hợp thú cưng (PetProfileView)."""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from petcare.services.appointment_service import AppointmentService
from petcare.services.auth_service import AuthSession
from petcare.services.exam_service import ExamService
from petcare.services.pet_service import PetService
from petcare.services.vaccination_service import VaccinationService
from petcare.services.visit_service import VisitService
from petcare.ui.common import DataTable, HeaderBar, show_error
from petcare.ui.theme import format_vnd, COLOR_CARD, COLOR_PRIMARY


class PetProfileView(ttk.Frame):
    """Xem toàn diện thông tin một thú cưng và các lịch sử khám, tiêm, hẹn, dịch vụ."""

    def __init__(
        self,
        parent,
        pet_id: int,
        pet_service: PetService,
        exam_service: ExamService,
        vaccination_service: VaccinationService,
        appointment_service: AppointmentService,
        visit_service: VisitService,
        session: AuthSession,
        on_back: Callable[[], None],
    ):
        super().__init__(parent, padding=16)
        self.pet_id = pet_id
        self.pet_service = pet_service
        self.exam_service = exam_service
        self.vaccination_service = vaccination_service
        self.appointment_service = appointment_service
        self.visit_service = visit_service
        self.session = session
        self.on_back = on_back

        # Header và nút quay lại
        header_frame = ttk.Frame(self)
        header_frame.pack(fill="x", pady=(0, 12))
        ttk.Button(header_frame, text="← Quay lại", command=on_back).pack(side="left", padx=(0, 12))
        ttk.Label(header_frame, text="Hồ sơ Bệnh án & Lịch sử Thú cưng", style="Header.TLabel").pack(side="left")

        # Thẻ thông tin tổng quan của thú cưng
        self.card_info = ttk.Frame(self, padding=16, style="Card.TFrame")
        self.card_info.pack(fill="x", pady=(0, 16))

        # Notebook chứa các tab lịch sử
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        # Tab 1: Khám bệnh
        self.tab_exams = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_exams, text="  Hồ sơ Khám bệnh  ")
        self.table_exams = DataTable(
            self.tab_exams,
            columns=("date", "service", "symptoms", "diagnosis", "medicines", "price"),
            headings=("Ngày khám", "Gói khám", "Triệu chứng", "Chẩn đoán", "Đơn thuốc", "Chi phí"),
            widths=(95, 140, 180, 180, 160, 100),
        )
        self.table_exams.pack(fill="both", expand=True)

        # Tab 2: Tiêm phòng
        self.tab_vaccines = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_vaccines, text="  Lịch sử Tiêm phòng  ")
        self.table_vaccines = DataTable(
            self.tab_vaccines,
            columns=("date", "vaccine", "service", "next_due", "reminder", "price"),
            headings=("Ngày tiêm", "Tên vaccine", "Dịch vụ", "Hẹn tiêm nhắc", "Trạng thái nhắc", "Chi phí"),
            widths=(95, 160, 140, 110, 120, 100),
        )
        self.table_vaccines.pack(fill="both", expand=True)

        # Tab 3: Lịch hẹn
        self.tab_appts = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_appts, text="  Lịch hẹn  ")
        self.table_appts = DataTable(
            self.tab_appts,
            columns=("sched_at", "type", "status", "note"),
            headings=("Thời gian hẹn", "Loại dịch vụ", "Trạng thái", "Ghi chú"),
            widths=(130, 140, 110, 240),
        )
        self.table_appts.pack(fill="both", expand=True)

        # Tab 4: Toàn bộ lượt dịch vụ
        self.tab_visits = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_visits, text="  Lượt Dịch vụ & Chi phí  ")
        self.table_visits = DataTable(
            self.tab_visits,
            columns=("date", "service", "category", "price"),
            headings=("Ngày thực hiện", "Tên dịch vụ", "Phân loại", "Chi phí"),
            widths=(110, 180, 120, 120),
        )
        self.table_visits.pack(fill="both", expand=True)

        self.load_data()

    def load_data(self) -> None:
        try:
            pet = self.pet_service.get_pet(self.session, self.pet_id)
            if not pet:
                show_error("Lỗi", "Không tìm thấy hồ sơ thú cưng")
                return

            # Hiển thị thông tin tổng quan
            for widget in self.card_info.winfo_children():
                widget.destroy()

            sex_map = {"male": "Đực", "female": "Cái", "unknown": "Chưa rõ"}
            sex_text = sex_map.get(pet["sex"], pet["sex"])
            weight_text = f"{pet['weight_kg']:.1f} kg" if pet["weight_kg"] is not None else "Chưa cân"
            birth_text = pet["birth_date"] or "Chưa rõ"
            status_text = "Đang theo dõi" if pet["active"] else "Ngừng theo dõi"

            col1 = ttk.Frame(self.card_info, style="Card.TFrame")
            col1.pack(side="left", fill="both", expand=True)
            ttk.Label(col1, text=f"{pet['name']} ({pet['species']})", font=("Segoe UI", 16, "bold"), foreground=COLOR_PRIMARY).pack(anchor="w")
            ttk.Label(col1, text=f"Giống: {pet['breed'] or 'Chưa rõ'} | Giới tính: {sex_text} | Cân nặng: {weight_text}", style="Muted.TLabel").pack(anchor="w", pady=(2, 0))
            ttk.Label(col1, text=f"Ngày sinh: {birth_text} | Màu lông: {pet['coat_color'] or 'Chưa rõ'} | Trạng thái: {status_text}").pack(anchor="w", pady=(2, 0))

            col2 = ttk.Frame(self.card_info, style="Card.TFrame")
            col2.pack(side="right", fill="both", padx=(20, 0))
            ttk.Label(col2, text="Thông tin Chủ nuôi", style="SubHeader.TLabel").pack(anchor="w")
            ttk.Label(col2, text=f"Chủ sở hữu: {pet['owner_name']}").pack(anchor="w")
            ttk.Label(col2, text=f"Số điện thoại: {pet['owner_phone']}", style="Muted.TLabel").pack(anchor="w")

            # 1. Tải hồ sơ khám
            self.table_exams.clear()
            exams = self.exam_service.get_pet_exams(self.session, self.pet_id)
            for ex in exams:
                self.table_exams.insert_row(
                    (
                        ex["exam_date"],
                        ex["service_name"],
                        ex["symptoms"],
                        ex["diagnosis"],
                        ex["medicines"] or "Không có",
                        format_vnd(ex["unit_price_vnd"]),
                    )
                )

            # 2. Tải hồ sơ tiêm
            self.table_vaccines.clear()
            vaccines = self.vaccination_service.get_pet_vaccinations(self.session, self.pet_id)
            for vac in vaccines:
                rem_text = "Đã xử lý" if vac["reminder_resolved"] else "Chưa nhắc"
                self.table_vaccines.insert_row(
                    (
                        vac["injection_date"],
                        vac["vaccine_name"],
                        vac["service_name"],
                        vac["next_due_date"] or "-",
                        rem_text,
                        format_vnd(vac["unit_price_vnd"]),
                    )
                )

            # 3. Tải lịch hẹn
            self.table_appts.clear()
            appts = self.appointment_service.get_pet_appointments(self.session, self.pet_id)
            status_map = {"planned": "Đang lên lịch", "completed": "Đã hoàn thành", "cancelled": "Đã hủy"}
            for ap in appts:
                self.table_appts.insert_row(
                    (
                        ap["scheduled_at"],
                        ap["type"],
                        status_map.get(ap["status"], ap["status"]),
                        ap["note"] or "-",
                    )
                )

            # 4. Tải các lượt dịch vụ
            self.table_visits.clear()
            visits = self.visit_service.get_pet_visits(self.session, self.pet_id)
            for vi in visits:
                self.table_visits.insert_row(
                    (
                        vi["performed_at"],
                        vi["service_name"],
                        vi["service_category"],
                        format_vnd(vi["unit_price_vnd"]),
                    )
                )

        except Exception as e:
            show_error("Lỗi tải hồ sơ", str(e))

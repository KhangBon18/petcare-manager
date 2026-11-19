"""Màn hình quản lý lịch hẹn (AppointmentsView)."""

from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk

from petcare.services.appointment_service import AppointmentService
from petcare.services.auth_service import AuthSession
from petcare.services.pet_service import PetService
from petcare.ui.common import DataTable, HeaderBar, show_confirm, show_error, show_info


class AppointmentsView(ttk.Frame):
    """Giao diện quản lý đặt lịch hẹn khám và chăm sóc thú cưng."""

    def __init__(
        self,
        parent,
        appointment_service: AppointmentService,
        pet_service: PetService,
        session: AuthSession,
    ):
        super().__init__(parent, padding=16)
        self.appointment_service = appointment_service
        self.pet_service = pet_service
        self.session = session

        HeaderBar(
            self,
            title="Quản lý Lịch hẹn",
            subtitle="Đặt lịch khám, tiêm chủng và chăm sóc spa (Lịch hẹn không tự phát sinh phí)",
        )

        # Thanh công cụ và bộ lọc
        filter_bar = ttk.Frame(self)
        filter_bar.pack(fill="x", pady=(0, 12))

        ttk.Button(
            filter_bar,
            text="+ Đặt lịch hẹn mới",
            style="Primary.TButton",
            command=self._show_create_dialog,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            filter_bar,
            text="Đánh dấu Hoàn thành",
            style="Success.TButton",
            command=lambda: self._update_status("completed"),
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            filter_bar,
            text="Hủy lịch hẹn",
            style="Danger.TButton",
            command=lambda: self._update_status("cancelled"),
        ).pack(side="left", padx=(0, 16))

        ttk.Label(filter_bar, text="Trạng thái:").pack(side="left", padx=(0, 6))
        self.cbo_status = ttk.Combobox(
            filter_bar,
            values=["Tất cả", "planned (Đang lên lịch)", "completed (Đã xong)", "cancelled (Đã hủy)"],
            width=20,
            state="readonly",
        )
        self.cbo_status.set("Tất cả")
        self.cbo_status.pack(side="left", padx=(0, 8))
        self.cbo_status.bind("<<ComboboxSelected>>", lambda e: self.load_data())

        ttk.Button(filter_bar, text="Làm mới", command=self.load_data).pack(side="left")

        # Bảng danh sách lịch hẹn
        columns = ("id", "scheduled_at", "pet_name", "owner_name", "owner_phone", "type", "status", "note")
        headings = ("ID", "Thời gian hẹn", "Thú cưng", "Chủ nuôi", "Số điện thoại", "Loại dịch vụ hẹn", "Trạng thái", "Ghi chú")
        widths = (40, 130, 110, 130, 120, 150, 120, 200)

        self.table = DataTable(self, columns=columns, headings=headings, widths=widths)
        self.table.pack(fill="both", expand=True)

        self.load_data()

    def load_data(self) -> None:
        self.table.clear()
        st_val = self.cbo_status.get()
        status_filter = None
        if "planned" in st_val:
            status_filter = "planned"
        elif "completed" in st_val:
            status_filter = "completed"
        elif "cancelled" in st_val:
            status_filter = "cancelled"

        try:
            appointments = self.appointment_service.list_appointments(self.session, status=status_filter)
            status_map = {
                "planned": "Đang lên lịch",
                "completed": "Đã hoàn thành",
                "cancelled": "Đã hủy",
            }
            for a in appointments:
                self.table.insert_row(
                    (
                        a["id"],
                        a["scheduled_at"],
                        a["pet_name"],
                        a["owner_name"],
                        a["owner_phone"],
                        a["type"],
                        status_map.get(a["status"], a["status"]),
                        a["note"] or "-",
                    ),
                    raw_data=a,
                )
        except Exception as e:
            show_error("Lỗi tải dữ liệu", str(e))

    def _show_create_dialog(self) -> None:
        try:
            pets = self.pet_service.list_pets(self.session, active_only=True)
            if not pets:
                show_error("Chưa có thú cưng", "Vui lòng thêm thú cưng trước khi đặt lịch hẹn")
                return
        except Exception as e:
            show_error("Lỗi", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title("Đặt lịch hẹn mới")
        dlg.geometry("480x420")
        dlg.transient(self)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=20)
        frame.pack(fill="both", expand=True)

        # Chọn thú cưng
        ttk.Label(frame, text="Thú cưng hẹn khám/chăm sóc:").pack(anchor="w", pady=(0, 2))
        pet_options = [f"{p['id']}: {p['name']} ({p['species']} - Chủ: {p['owner_name']})" for p in pets]
        cbo_pet = ttk.Combobox(frame, values=pet_options, state="readonly")
        cbo_pet.current(0)
        cbo_pet.pack(fill="x", pady=(0, 10))

        # Loại lịch hẹn
        ttk.Label(frame, text="Loại hẹn dịch vụ:").pack(anchor="w", pady=(0, 2))
        cbo_type = ttk.Combobox(
            frame,
            values=["Khám tổng quát", "Khám bệnh chuyên khoa", "Tiêm vaccine", "Tắm spa & cắt tỉa lông", "Tẩy giun định kỳ", "Tái khám"],
        )
        cbo_type.set("Khám tổng quát")
        cbo_type.pack(fill="x", pady=(0, 10))

        # Thời gian hẹn
        suggested_time = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d 09:00")
        ttk.Label(frame, text="Thời gian hẹn (YYYY-MM-DD HH:MM):").pack(anchor="w", pady=(0, 2))
        ent_time = ttk.Entry(frame)
        ent_time.insert(0, suggested_time)
        ent_time.pack(fill="x", pady=(0, 10))

        # Ghi chú
        ttk.Label(frame, text="Ghi chú yêu cầu của khách hàng:").pack(anchor="w", pady=(0, 2))
        ent_note = ttk.Entry(frame)
        ent_note.pack(fill="x", pady=(0, 14))

        ttk.Label(
            frame,
            text="* Lưu ý: Lịch hẹn chỉ lưu kế hoạch tiếp đón, không phát sinh chi phí tại thời điểm này.",
            style="Muted.TLabel",
            wraplength=420,
        ).pack(anchor="w", pady=(0, 16))

        def save():
            p_val = cbo_pet.get()
            if not p_val:
                show_error("Lỗi", "Vui lòng chọn thú cưng")
                return

            pet_id = int(p_val.split(":")[0])
            try:
                self.appointment_service.create_appointment(
                    self.session,
                    {
                        "pet_id": pet_id,
                        "type": cbo_type.get().strip(),
                        "scheduled_at": ent_time.get().strip(),
                        "note": ent_note.get().strip(),
                    },
                )
                show_info("Thành công", "Đã đặt lịch hẹn thành công!")
                dlg.destroy()
                self.load_data()
            except Exception as e:
                show_error("Lỗi đặt hẹn", str(e))

        ttk.Button(frame, text="Xác nhận đặt lịch", style="Primary.TButton", command=save).pack(fill="x")

    def _update_status(self, new_status: str) -> None:
        selected = self.table.get_selected_data()
        if not selected:
            show_error("Thông báo", "Vui lòng chọn lịch hẹn từ bảng danh sách")
            return

        status_text = "Hoàn thành" if new_status == "completed" else "Hủy"
        if not show_confirm("Xác nhận", f"Bạn có chắc muốn chuyển lịch hẹn #{selected['id']} sang trạng thái '{status_text}'?"):
            return

        try:
            self.appointment_service.update_status(self.session, selected["id"], new_status)
            show_info("Thành công", f"Đã cập nhật lịch hẹn thành '{status_text}'!")
            self.load_data()
        except Exception as e:
            show_error("Lỗi cập nhật", str(e))

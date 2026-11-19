"""Màn hình quản lý hóa đơn và thanh toán trực tiếp (InvoicesView)."""

import tkinter as tk
from tkinter import ttk

from petcare.services.auth_service import AuthSession
from petcare.services.invoice_service import InvoiceService
from petcare.services.owner_service import OwnerService
from petcare.services.visit_service import VisitService
from petcare.ui.common import DataTable, HeaderBar, show_confirm, show_error, show_info
from petcare.ui.theme import format_vnd, COLOR_SUCCESS


class InvoicesView(ttk.Frame):
    """Giao diện lập hóa đơn từ các lượt dịch vụ chưa thanh toán, thanh toán và đối soát."""

    def __init__(
        self,
        parent,
        invoice_service: InvoiceService,
        visit_service: VisitService,
        owner_service: OwnerService,
        session: AuthSession,
    ):
        super().__init__(parent, padding=16)
        self.invoice_service = invoice_service
        self.visit_service = visit_service
        self.owner_service = owner_service
        self.session = session

        HeaderBar(
            self,
            title="Quản lý Hóa đơn & Thanh toán",
            subtitle="Lập hóa đơn từ các lượt chưa tính tiền, thanh toán trực tiếp tại quầy và bảo vệ doanh thu",
        )

        # Thanh công cụ và lọc
        filter_bar = ttk.Frame(self)
        filter_bar.pack(fill="x", pady=(0, 12))

        ttk.Button(
            filter_bar,
            text="+ Lập hóa đơn mới",
            style="Primary.TButton",
            command=self._show_create_invoice_dialog,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            filter_bar,
            text="Thanh toán trực tiếp",
            style="Success.TButton",
            command=self._pay_selected_invoice,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            filter_bar,
            text="Hủy hóa đơn (Unpaid)",
            style="Danger.TButton",
            command=self._cancel_selected_invoice,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            filter_bar,
            text="Xem chi tiết",
            command=self._view_invoice_detail,
        ).pack(side="left", padx=(0, 16))

        ttk.Label(filter_bar, text="Trạng thái:").pack(side="left", padx=(0, 6))
        self.cbo_status = ttk.Combobox(
            filter_bar,
            values=["Tất cả", "unpaid (Chưa thanh toán)", "paid (Đã thanh toán)", "cancelled (Đã hủy)"],
            width=20,
            state="readonly",
        )
        self.cbo_status.set("Tất cả")
        self.cbo_status.pack(side="left", padx=(0, 8))
        self.cbo_status.bind("<<ComboboxSelected>>", lambda e: self.load_data())

        ttk.Button(filter_bar, text="Làm mới", command=self.load_data).pack(side="left")

        # Bảng danh sách hóa đơn
        columns = ("id", "created_at", "owner_name", "phone", "item_count", "total_amount", "status", "paid_at")
        headings = ("ID", "Ngày lập", "Chủ nuôi", "Số điện thoại", "Số dịch vụ", "Tổng tiền (VND)", "Trạng thái", "Ngày thanh toán")
        widths = (40, 100, 150, 120, 90, 130, 130, 130)

        self.table = DataTable(
            self,
            columns=columns,
            headings=headings,
            widths=widths,
            on_double_click=lambda row: self._view_invoice_detail(),
        )
        self.table.pack(fill="both", expand=True)

        self.load_data()

    def load_data(self) -> None:
        self.table.clear()
        st_val = self.cbo_status.get()
        status_filter = None
        if "unpaid" in st_val:
            status_filter = "unpaid"
        elif "paid" in st_val:
            status_filter = "paid"
        elif "cancelled" in st_val:
            status_filter = "cancelled"

        try:
            invoices = self.invoice_service.list_invoices(self.session, status=status_filter)
            status_map = {
                "unpaid": "Chưa thanh toán",
                "paid": "Đã thanh toán",
                "cancelled": "Đã hủy",
            }
            for inv in invoices:
                created_text = inv["created_at"][:10] if inv.get("created_at") else ""
                paid_text = inv["paid_at"][:16].replace("T", " ") if inv.get("paid_at") else "-"

                self.table.insert_row(
                    (
                        inv["id"],
                        created_text,
                        inv["owner_name"],
                        inv["owner_phone"],
                        inv["item_count"],
                        format_vnd(inv["total_amount_vnd"]),
                        status_map.get(inv["status"], inv["status"]),
                        paid_text,
                    ),
                    raw_data=inv,
                )
        except Exception as e:
            show_error("Lỗi tải dữ liệu", str(e))

    def _show_create_invoice_dialog(self) -> None:
        try:
            owners = self.owner_service.list_owners(self.session, active_only=True)
            if not owners:
                show_error("Chưa có chủ nuôi", "Chưa có chủ nuôi nào trong hệ thống")
                return
        except Exception as e:
            show_error("Lỗi", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title("Lập hóa đơn thanh toán mới")
        dlg.geometry("640x560")
        dlg.transient(self)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=20)
        frame.pack(fill="both", expand=True)

        # Chọn chủ nuôi
        ttk.Label(frame, text="Chọn chủ nuôi cần lập hóa đơn:").pack(anchor="w", pady=(0, 2))
        owner_options = [f"{o['id']}: {o['full_name']} - SĐT: {o['phone']}" for o in owners]
        cbo_owner = ttk.Combobox(frame, values=owner_options, state="readonly")
        cbo_owner.current(0)
        cbo_owner.pack(fill="x", pady=(0, 10))

        # Khung danh sách các lượt chưa tính tiền
        lbl_unbilled = ttk.Label(frame, text="Các lượt dịch vụ chưa thanh toán của chủ nuôi:")
        lbl_unbilled.pack(anchor="w", pady=(0, 4))

        tree_visits = ttk.Treeview(
            frame,
            columns=("id", "date", "pet", "service", "price"),
            show="headings",
            selectmode="extended",
            height=8,
        )
        tree_visits.heading("id", text="ID")
        tree_visits.heading("date", text="Ngày thực hiện")
        tree_visits.heading("pet", text="Thú cưng")
        tree_visits.heading("service", text="Dịch vụ")
        tree_visits.heading("price", text="Đơn giá (VND)")

        tree_visits.column("id", width=40, anchor="w")
        tree_visits.column("date", width=100, anchor="w")
        tree_visits.column("pet", width=110, anchor="w")
        tree_visits.column("service", width=180, anchor="w")
        tree_visits.column("price", width=110, anchor="w")
        tree_visits.pack(fill="both", expand=True, pady=(0, 10))

        lbl_total = ttk.Label(frame, text="Tổng tiền tạm tính: 0 đ", font=("Segoe UI", 11, "bold"), foreground=COLOR_SUCCESS)
        lbl_total.pack(anchor="e", pady=(0, 10))

        ttk.Label(frame, text="Ghi chú hóa đơn (tùy chọn):").pack(anchor="w", pady=(0, 2))
        ent_note = ttk.Entry(frame)
        ent_note.pack(fill="x", pady=(0, 16))

        unbilled_cache: dict[str, dict] = {}

        def refresh_owner_visits(e=None):
            tree_visits.delete(*tree_visits.get_children())
            unbilled_cache.clear()
            owner_val = cbo_owner.get()
            if not owner_val:
                return
            sel_owner_id = int(owner_val.split(":")[0])
            try:
                unbilled = self.visit_service.get_unbilled_visits_by_owner(self.session, sel_owner_id)
                for v in unbilled:
                    item_id = tree_visits.insert(
                        "",
                        "end",
                        values=(v["id"], v["performed_at"][:10], v["pet_name"], v["service_name"], format_vnd(v["unit_price_vnd"])),
                    )
                    unbilled_cache[item_id] = v
                # Tự động chọn tất cả các lượt
                for item_id in tree_visits.get_children():
                    tree_visits.selection_add(item_id)
                recalc_total()
            except Exception as ex:
                show_error("Lỗi", str(ex))

        def recalc_total(e=None):
            sel_items = tree_visits.selection()
            tot = sum(unbilled_cache[item]["unit_price_vnd"] for item in sel_items if item in unbilled_cache)
            lbl_total.config(text=f"Tổng tiền tạm tính ({len(sel_items)} lượt): {format_vnd(tot)}")

        cbo_owner.bind("<<ComboboxSelected>>", refresh_owner_visits)
        tree_visits.bind("<<TreeviewSelect>>", recalc_total)
        refresh_owner_visits()

        def save_invoice():
            sel_items = tree_visits.selection()
            if not sel_items:
                show_error("Chưa chọn dịch vụ", "Vui lòng chọn ít nhất một lượt dịch vụ để lập hóa đơn")
                return

            visit_ids = [unbilled_cache[item]["id"] for item in sel_items if item in unbilled_cache]
            owner_id = int(cbo_owner.get().split(":")[0])
            note = ent_note.get().strip() or None

            try:
                new_inv_id = self.invoice_service.create_invoice(
                    self.session,
                    owner_id=owner_id,
                    visit_ids=visit_ids,
                    note=note,
                )
                show_info("Thành công", f"Đã lập hóa đơn #{new_inv_id} thành công!")
                dlg.destroy()
                self.load_data()
            except Exception as ex:
                show_error("Lỗi lập hóa đơn", str(ex))

        ttk.Button(frame, text="Tạo hóa đơn", style="Primary.TButton", command=save_invoice).pack(fill="x")

    def _pay_selected_invoice(self) -> None:
        selected = self.table.get_selected_data()
        if not selected:
            show_error("Thông báo", "Vui lòng chọn hóa đơn cần thanh toán")
            return

        inv_id = selected["id"]
        status = selected["status"]
        if status == "paid":
            show_info("Thông báo", "Hóa đơn này đã được thanh toán trước đó.")
            return
        if status == "cancelled":
            show_error("Lỗi", "Không thể thanh toán hóa đơn đã bị hủy.")
            return

        total_vnd = selected["total_amount_vnd"]
        if not show_confirm(
            "Xác nhận thanh toán",
            f"Xác nhận khách hàng '{selected['owner_name']}' thanh toán trực tiếp số tiền:\n\n"
            f"👉 {format_vnd(total_vnd)}\n\n"
            "Hóa đơn sau khi thanh toán sẽ trở thành bất biến (không thể sửa hoặc hủy).",
        ):
            return

        try:
            res = self.invoice_service.pay_invoice(self.session, inv_id)
            if res == "paid":
                show_info("Thành công", f"Thanh toán hóa đơn #{inv_id} thành công!")
            else:
                show_info("Thông báo", "Hóa đơn đã được thanh toán trước đó.")
            self.load_data()
        except Exception as e:
            show_error("Lỗi thanh toán", str(e))

    def _cancel_selected_invoice(self) -> None:
        selected = self.table.get_selected_data()
        if not selected:
            show_error("Thông báo", "Vui lòng chọn hóa đơn cần hủy")
            return

        inv_id = selected["id"]
        if selected["status"] == "paid":
            show_error("Không được phép", "Không thể hủy hóa đơn đã thanh toán thành công.")
            return
        if selected["status"] == "cancelled":
            show_info("Thông báo", "Hóa đơn này đã bị hủy trước đó.")
            return

        if not show_confirm(
            "Xác nhận hủy hóa đơn",
            f"Bạn có chắc muốn hủy hóa đơn #{inv_id}?\n"
            "Các lượt dịch vụ bên trong sẽ được giải phóng để có thể lập vào hóa đơn khác.",
        ):
            return

        try:
            self.invoice_service.cancel_invoice(self.session, inv_id)
            show_info("Thành công", f"Đã hủy hóa đơn #{inv_id} và giải phóng các lượt dịch vụ.")
            self.load_data()
        except Exception as e:
            show_error("Lỗi hủy hóa đơn", str(e))

    def _view_invoice_detail(self) -> None:
        selected = self.table.get_selected_data()
        if not selected:
            show_error("Thông báo", "Vui lòng chọn hóa đơn để xem chi tiết")
            return

        try:
            inv = self.invoice_service.get_invoice(self.session, selected["id"])
            if not inv:
                show_error("Lỗi", "Không tìm thấy thông tin hóa đơn")
                return
        except Exception as e:
            show_error("Lỗi", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Chi tiết Hóa đơn #{inv['id']}")
        dlg.geometry("540x480")
        dlg.transient(self)

        frame = ttk.Frame(dlg, padding=20)
        frame.pack(fill="both", expand=True)

        status_map = {"unpaid": "Chưa thanh toán", "paid": "Đã thanh toán", "cancelled": "Đã hủy"}
        ttk.Label(frame, text=f"HÓA ĐƠN DỊCH VỤ #{inv['id']}", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"Khách hàng: {inv['owner_name']} | SĐT: {inv['owner_phone']}").pack(anchor="w", pady=(2, 0))
        ttk.Label(frame, text=f"Địa chỉ: {inv.get('owner_address', '')}", style="Muted.TLabel").pack(anchor="w", pady=(0, 6))

        info_box = ttk.Frame(frame, padding=8, style="Card.TFrame")
        info_box.pack(fill="x", pady=(0, 10))
        paid_text = inv["paid_at"].replace("T", " ") if inv.get("paid_at") else "Chưa thanh toán"
        ttk.Label(info_box, text=f"Ngày tạo: {inv['created_at'][:10]} | Trạng thái: {status_map.get(inv['status'], inv['status'])}").pack(anchor="w")
        ttk.Label(info_box, text=f"Thời gian thanh toán: {paid_text}").pack(anchor="w")
        if inv.get("note"):
            ttk.Label(info_box, text=f"Ghi chú: {inv['note']}", style="Muted.TLabel").pack(anchor="w")

        ttk.Label(frame, text="Các khoản dịch vụ chi tiết:", style="SubHeader.TLabel").pack(anchor="w", pady=(4, 2))

        tree_items = ttk.Treeview(
            frame,
            columns=("idx", "pet", "service", "amount"),
            show="headings",
            height=6,
        )
        tree_items.heading("idx", text="STT")
        tree_items.heading("pet", text="Thú cưng")
        tree_items.heading("service", text="Dịch vụ")
        tree_items.heading("amount", text="Thành tiền (VND)")

        tree_items.column("idx", width=40, anchor="w")
        tree_items.column("pet", width=120, anchor="w")
        tree_items.column("service", width=200, anchor="w")
        tree_items.column("amount", width=120, anchor="w")
        tree_items.pack(fill="both", expand=True, pady=(0, 10))

        for idx, item in enumerate(inv.get("items", []), start=1):
            tree_items.insert(
                "",
                "end",
                values=(idx, item["pet_name_snapshot"], item["service_name_snapshot"], format_vnd(item["amount_vnd"])),
            )

        ttk.Label(
            frame,
            text=f"TỔNG CỘNG: {format_vnd(inv['total_amount_vnd'])}",
            font=("Segoe UI", 13, "bold"),
            foreground=COLOR_SUCCESS,
        ).pack(anchor="e", pady=(6, 12))

        ttk.Button(frame, text="Đóng", command=dlg.destroy).pack(side="right")

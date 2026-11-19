"""Màn hình quản lý chủ nuôi (OwnersView)."""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from petcare.services.auth_service import AuthSession
from petcare.services.owner_service import OwnerService
from petcare.ui.common import DataTable, HeaderBar, show_confirm, show_error, show_info


class OwnersView(ttk.Frame):
    """Màn hình danh sách, tìm kiếm và cập nhật chủ nuôi."""

    def __init__(
        self,
        parent,
        owner_service: OwnerService,
        session: AuthSession,
        on_view_owner_pets: Callable[[int, str], None] | None = None,
    ):
        super().__init__(parent, padding=16)
        self.owner_service = owner_service
        self.session = session
        self.on_view_owner_pets = on_view_owner_pets

        HeaderBar(
            self,
            title="Quản lý Chủ nuôi",
            subtitle="Danh sách khách hàng, thông tin liên hệ và lịch sử nuôi thú cưng",
        )

        # Thanh tìm kiếm và bộ lọc
        filter_bar = ttk.Frame(self)
        filter_bar.pack(fill="x", pady=(0, 12))

        ttk.Label(filter_bar, text="Tìm kiếm:").pack(side="left", padx=(0, 6))
        self.ent_search = ttk.Entry(filter_bar, width=28)
        self.ent_search.pack(side="left", padx=(0, 8))
        self.ent_search.bind("<Return>", lambda e: self.load_data())

        ttk.Button(filter_bar, text="Tìm kiếm", command=self.load_data).pack(side="left", padx=(0, 8))
        ttk.Button(filter_bar, text="Đặt lại", command=self._reset_search).pack(side="left", padx=(0, 16))

        # Thanh công cụ thao tác
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 12))

        ttk.Button(
            toolbar,
            text="+ Thêm chủ nuôi",
            style="Primary.TButton",
            command=self._show_add_dialog,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Sửa thông tin",
            command=self._show_edit_dialog,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Ngừng theo dõi / Xóa",
            style="Danger.TButton",
            command=self._delete_or_deactivate,
        ).pack(side="left", padx=(0, 8))

        if self.on_view_owner_pets:
            ttk.Button(
                toolbar,
                text="Xem thú cưng của chủ",
                command=self._view_pets,
            ).pack(side="left", padx=(0, 8))

        # Bảng dữ liệu
        columns = ("id", "full_name", "phone", "address", "active", "created_at")
        headings = ("ID", "Họ và tên", "Số điện thoại", "Địa chỉ", "Trạng thái", "Ngày tạo")
        widths = (50, 180, 130, 260, 130, 130)

        self.table = DataTable(
            self,
            columns=columns,
            headings=headings,
            widths=widths,
            on_double_click=lambda row: self._show_edit_dialog(),
        )
        self.table.pack(fill="both", expand=True)

        self.load_data()

    def _reset_search(self) -> None:
        self.ent_search.delete(0, "end")
        self.load_data()

    def load_data(self) -> None:
        self.table.clear()
        kw = self.ent_search.get().strip()
        try:
            owners = self.owner_service.search_owners(self.session, keyword=kw, active_only=False)
            for o in owners:
                status_text = "Đang theo dõi" if o["active"] else "Đã ngừng"
                created_text = o["created_at"][:10] if o.get("created_at") else ""
                self.table.insert_row(
                    (o["id"], o["full_name"], o["phone"], o["address"], status_text, created_text),
                    raw_data=o,
                )
        except Exception as e:
            show_error("Lỗi tải dữ liệu", str(e))

    def _show_add_dialog(self) -> None:
        self._open_form_dialog(title="Thêm chủ nuôi mới", existing=None)

    def _show_edit_dialog(self) -> None:
        selected = self.table.get_selected_data()
        if not selected:
            show_error("Thông báo", "Vui lòng chọn chủ nuôi cần sửa từ bảng danh sách")
            return
        self._open_form_dialog(title="Sửa thông tin chủ nuôi", existing=selected)

    def _open_form_dialog(self, title: str, existing: dict | None) -> None:
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.geometry("440x360")
        dlg.transient(self)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Họ và tên chủ nuôi:").pack(anchor="w", pady=(0, 2))
        ent_name = ttk.Entry(frame)
        ent_name.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Số điện thoại:").pack(anchor="w", pady=(0, 2))
        ent_phone = ttk.Entry(frame)
        ent_phone.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Địa chỉ liên hệ:").pack(anchor="w", pady=(0, 2))
        ent_addr = ttk.Entry(frame)
        ent_addr.pack(fill="x", pady=(0, 10))

        var_active = tk.IntVar(value=1)
        if existing:
            ent_name.insert(0, existing["full_name"])
            ent_phone.insert(0, existing["phone"])
            ent_addr.insert(0, existing["address"])
            var_active.set(existing["active"])
            chk_active = ttk.Checkbutton(frame, text="Đang theo dõi (Active)", variable=var_active)
            chk_active.pack(anchor="w", pady=(0, 16))
        else:
            frame.pack_propagate(False)

        def save():
            name = ent_name.get().strip()
            phone = ent_phone.get().strip()
            addr = ent_addr.get().strip()
            try:
                if existing:
                    self.owner_service.update_owner(
                        self.session,
                        owner_id=existing["id"],
                        data={"full_name": name, "phone": phone, "address": addr, "active": var_active.get()},
                    )
                    show_info("Thành công", "Đã cập nhật thông tin chủ nuôi thành công!")
                else:
                    self.owner_service.create_owner(
                        self.session,
                        data={"full_name": name, "phone": phone, "address": addr},
                    )
                    show_info("Thành công", "Đã tạo chủ nuôi mới thành công!")
                dlg.destroy()
                self.load_data()
            except Exception as e:
                show_error("Lỗi lưu dữ liệu", str(e))

        ttk.Button(frame, text="Lưu thông tin", style="Primary.TButton", command=save).pack(fill="x", pady=(8, 0))

    def _delete_or_deactivate(self) -> None:
        selected = self.table.get_selected_data()
        if not selected:
            show_error("Thông báo", "Vui lòng chọn chủ nuôi từ bảng danh sách")
            return

        name = selected["full_name"]
        if not show_confirm(
            "Xác nhận",
            f"Bạn có muốn xóa hoặc ngừng theo dõi chủ nuôi '{name}'?\n"
            "(Nếu đã có thú cưng hoặc hóa đơn, hệ thống sẽ tự động chuyển sang ngừng theo dõi để bảo toàn dữ liệu lịch sử)",
        ):
            return

        try:
            res = self.owner_service.delete_or_deactivate_owner(self.session, selected["id"])
            if res == "deleted":
                show_info("Đã xóa", f"Đã xóa hoàn toàn chủ nuôi '{name}'.")
            else:
                show_info("Đã ngừng theo dõi", f"Chủ nuôi '{name}' đã có dữ liệu liên kết nên được chuyển sang trạng thái Ngừng theo dõi.")
            self.load_data()
        except Exception as e:
            show_error("Lỗi", str(e))

    def _view_pets(self) -> None:
        selected = self.table.get_selected_data()
        if not selected:
            show_error("Thông báo", "Vui lòng chọn chủ nuôi từ bảng danh sách")
            return
        if self.on_view_owner_pets:
            self.on_view_owner_pets(selected["id"], selected["full_name"])

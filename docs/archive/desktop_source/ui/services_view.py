"""Màn hình danh mục dịch vụ và giá (ServicesView)."""

import tkinter as tk
from tkinter import ttk

from petcare.services.auth_service import AuthSession
from petcare.services.catalog_service import CatalogService
from petcare.ui.common import DataTable, HeaderBar, show_confirm, show_error, show_info
from petcare.ui.theme import format_vnd


class ServicesView(ttk.Frame):
    """Màn hình danh mục dịch vụ, giá niêm yết và phân quyền Admin/Nhân viên."""

    def __init__(self, parent, catalog_service: CatalogService, session: AuthSession):
        super().__init__(parent, padding=16)
        self.catalog_service = catalog_service
        self.session = session

        HeaderBar(
            self,
            title="Danh mục Dịch vụ & Bảng giá",
            subtitle="Bảng giá khám bệnh, tiêm phòng và chăm sóc spa (Chỉ Admin có quyền đổi giá)",
        )

        # Thanh tìm kiếm
        filter_bar = ttk.Frame(self)
        filter_bar.pack(fill="x", pady=(0, 12))

        ttk.Label(filter_bar, text="Tìm kiếm:").pack(side="left", padx=(0, 6))
        self.ent_search = ttk.Entry(filter_bar, width=24)
        self.ent_search.pack(side="left", padx=(0, 8))
        self.ent_search.bind("<Return>", lambda e: self.load_data())

        ttk.Label(filter_bar, text="Phân loại:").pack(side="left", padx=(8, 6))
        self.cbo_cat = ttk.Combobox(
            filter_bar,
            values=["Tất cả", "Khám bệnh", "Tiêm phòng", "Chăm sóc", "Xét nghiệm"],
            width=12,
            state="readonly",
        )
        self.cbo_cat.set("Tất cả")
        self.cbo_cat.pack(side="left", padx=(0, 8))
        self.cbo_cat.bind("<<ComboboxSelected>>", lambda e: self.load_data())

        ttk.Button(filter_bar, text="Tìm kiếm", command=self.load_data).pack(side="left", padx=(0, 8))
        ttk.Button(filter_bar, text="Đặt lại", command=self._reset_filters).pack(side="left")

        # Thanh công cụ (Nút Thêm/Sửa chỉ hiện cho Admin)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 12))

        if self.session.is_admin():
            ttk.Button(
                toolbar,
                text="+ Thêm dịch vụ",
                style="Primary.TButton",
                command=self._show_add_dialog,
            ).pack(side="left", padx=(0, 8))

            ttk.Button(
                toolbar,
                text="Sửa thông tin / Đổi giá",
                command=self._show_edit_dialog,
            ).pack(side="left", padx=(0, 8))

            ttk.Button(
                toolbar,
                text="Ngừng cung cấp",
                style="Danger.TButton",
                command=self._deactivate_service,
            ).pack(side="left", padx=(0, 8))
        else:
            ttk.Label(
                toolbar,
                text="ℹ️ Nhân viên chỉ có quyền xem danh mục; liên hệ Admin để thay đổi giá.",
                style="Muted.TLabel",
            ).pack(side="left")

        # Bảng danh mục
        columns = ("id", "name", "category", "price", "status")
        headings = ("ID", "Tên dịch vụ", "Phân loại", "Giá niêm yết (VND)", "Trạng thái")
        widths = (50, 240, 140, 140, 130)

        self.table = DataTable(
            self,
            columns=columns,
            headings=headings,
            widths=widths,
            on_double_click=lambda row: self._show_edit_dialog() if self.session.is_admin() else None,
        )
        self.table.pack(fill="both", expand=True)

        self.load_data()

    def _reset_filters(self) -> None:
        self.ent_search.delete(0, "end")
        self.cbo_cat.set("Tất cả")
        self.load_data()

    def load_data(self) -> None:
        self.table.clear()
        kw = self.ent_search.get().strip()
        cat_filter = self.cbo_cat.get()
        cat = "" if cat_filter == "Tất cả" else cat_filter

        try:
            services = self.catalog_service.search_services(
                self.session, keyword=kw, category=cat, active_only=False
            )
            for s in services:
                status_text = "Đang áp dụng" if s["active"] else "Đã ngừng"
                self.table.insert_row(
                    (s["id"], s["name"], s["category"], format_vnd(s["price_vnd"]), status_text),
                    raw_data=s,
                )
        except Exception as e:
            show_error("Lỗi tải dữ liệu", str(e))

    def _show_add_dialog(self) -> None:
        self._open_form_dialog(title="Thêm dịch vụ mới", existing=None)

    def _show_edit_dialog(self) -> None:
        if not self.session.is_admin():
            show_error("Từ chối", "Chỉ Quản trị viên mới có quyền sửa dịch vụ")
            return

        selected = self.table.get_selected_data()
        if not selected:
            show_error("Thông báo", "Vui lòng chọn dịch vụ từ bảng danh sách")
            return
        self._open_form_dialog(title="Sửa thông tin dịch vụ", existing=selected)

    def _open_form_dialog(self, title: str, existing: dict | None) -> None:
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.geometry("420x360")
        dlg.transient(self)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Tên dịch vụ:").pack(anchor="w", pady=(0, 2))
        ent_name = ttk.Entry(frame)
        ent_name.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Phân loại:").pack(anchor="w", pady=(0, 2))
        cbo_cat = ttk.Combobox(
            frame,
            values=["Khám bệnh", "Tiêm phòng", "Chăm sóc", "Xét nghiệm", "Khác"],
        )
        cbo_cat.set("Khám bệnh")
        cbo_cat.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Giá dịch vụ (VND, số nguyên không âm):").pack(anchor="w", pady=(0, 2))
        ent_price = ttk.Entry(frame)
        ent_price.pack(fill="x", pady=(0, 10))

        var_active = tk.IntVar(value=1)
        if existing:
            ent_name.insert(0, existing["name"])
            cbo_cat.set(existing["category"])
            ent_price.insert(0, str(existing["price_vnd"]))
            var_active.set(existing["active"])
            ttk.Checkbutton(frame, text="Đang áp dụng (Active)", variable=var_active).pack(anchor="w", pady=(0, 14))

        def save():
            name = ent_name.get().strip()
            cat = cbo_cat.get().strip()
            price = ent_price.get().strip()
            data = {"name": name, "category": cat, "price_vnd": price}

            try:
                if existing:
                    data["active"] = var_active.get()
                    self.catalog_service.update_service(self.session, service_id=existing["id"], data=data)
                    show_info("Thành công", "Đã cập nhật dịch vụ thành công!")
                else:
                    self.catalog_service.create_service(self.session, data=data)
                    show_info("Thành công", "Đã tạo dịch vụ mới thành công!")
                dlg.destroy()
                self.load_data()
            except Exception as e:
                show_error("Lỗi lưu dịch vụ", str(e))

        ttk.Button(frame, text="Lưu dịch vụ", style="Primary.TButton", command=save).pack(fill="x", pady=(10, 0))

    def _deactivate_service(self) -> None:
        selected = self.table.get_selected_data()
        if not selected:
            show_error("Thông báo", "Vui lòng chọn dịch vụ cần ngừng áp dụng")
            return

        name = selected["name"]
        if not show_confirm("Xác nhận", f"Bạn có chắc muốn ngừng cung cấp dịch vụ '{name}'?"):
            return

        try:
            self.catalog_service.deactivate_service(self.session, selected["id"])
            show_info("Thành công", f"Đã ngừng cung cấp dịch vụ '{name}'.")
            self.load_data()
        except Exception as e:
            show_error("Lỗi", str(e))

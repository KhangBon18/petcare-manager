"""Màn hình quản lý thú cưng (PetsView)."""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from petcare.services.auth_service import AuthSession
from petcare.services.owner_service import OwnerService
from petcare.services.pet_service import PetService
from petcare.ui.common import DataTable, HeaderBar, show_confirm, show_error, show_info


class PetsView(ttk.Frame):
    """Màn hình danh sách, tìm kiếm và cập nhật thú cưng."""

    def __init__(
        self,
        parent,
        pet_service: PetService,
        owner_service: OwnerService,
        session: AuthSession,
        on_view_pet_profile: Callable[[int], None] | None = None,
        initial_owner_id: int | None = None,
    ):
        super().__init__(parent, padding=16)
        self.pet_service = pet_service
        self.owner_service = owner_service
        self.session = session
        self.on_view_pet_profile = on_view_pet_profile
        self.current_owner_filter = initial_owner_id

        HeaderBar(
            self,
            title="Quản lý Thú cưng",
            subtitle="Danh sách bệnh nhân thú cưng, thông tin giống loài, thể trạng và chủ nuôi",
        )

        # Thanh tìm kiếm và bộ lọc
        filter_bar = ttk.Frame(self)
        filter_bar.pack(fill="x", pady=(0, 12))

        ttk.Label(filter_bar, text="Tìm kiếm:").pack(side="left", padx=(0, 6))
        self.ent_search = ttk.Entry(filter_bar, width=22)
        self.ent_search.pack(side="left", padx=(0, 8))
        self.ent_search.bind("<Return>", lambda e: self.load_data())

        ttk.Label(filter_bar, text="Loài:").pack(side="left", padx=(8, 6))
        self.cbo_species = ttk.Combobox(
            filter_bar, values=["Tất cả", "Chó", "Mèo", "Khác"], width=10, state="readonly"
        )
        self.cbo_species.set("Tất cả")
        self.cbo_species.pack(side="left", padx=(0, 8))
        self.cbo_species.bind("<<ComboboxSelected>>", lambda e: self.load_data())

        ttk.Button(filter_bar, text="Tìm kiếm", command=self.load_data).pack(side="left", padx=(0, 8))
        ttk.Button(filter_bar, text="Đặt lại", command=self._reset_filters).pack(side="left", padx=(0, 16))

        # Thanh công cụ thao tác
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 12))

        ttk.Button(
            toolbar,
            text="+ Thêm thú cưng",
            style="Primary.TButton",
            command=self._show_add_dialog,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Sửa thông tin",
            command=self._show_edit_dialog,
        ).pack(side="left", padx=(0, 8))

        if self.on_view_pet_profile:
            ttk.Button(
                toolbar,
                text="Xem hồ sơ tổng hợp",
                command=self._view_profile,
            ).pack(side="left", padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Ngừng theo dõi / Xóa",
            style="Danger.TButton",
            command=self._delete_or_deactivate,
        ).pack(side="left", padx=(0, 8))

        # Bảng dữ liệu
        columns = ("id", "name", "species", "breed", "sex", "weight", "birth_date", "owner_name", "status")
        headings = ("ID", "Tên thú cưng", "Loài", "Giống", "Giới tính", "Cân nặng (kg)", "Ngày sinh", "Chủ nuôi", "Trạng thái")
        widths = (40, 120, 70, 110, 70, 90, 95, 140, 100)

        self.table = DataTable(
            self,
            columns=columns,
            headings=headings,
            widths=widths,
            on_double_click=lambda row: self._view_profile() if self.on_view_pet_profile else self._show_edit_dialog(),
        )
        self.table.pack(fill="both", expand=True)

        self.load_data()

    def _reset_filters(self) -> None:
        self.ent_search.delete(0, "end")
        self.cbo_species.set("Tất cả")
        self.current_owner_filter = None
        self.load_data()

    def set_owner_filter(self, owner_id: int, owner_name: str) -> None:
        self.current_owner_filter = owner_id
        self.ent_search.delete(0, "end")
        self.cbo_species.set("Tất cả")
        self.load_data()

    def load_data(self) -> None:
        self.table.clear()
        kw = self.ent_search.get().strip()
        sp_filter = self.cbo_species.get()
        species = "" if sp_filter == "Tất cả" else sp_filter

        try:
            if self.current_owner_filter:
                pets = self.pet_service.get_pets_by_owner(self.session, self.current_owner_filter, active_only=False)
            else:
                pets = self.pet_service.search_pets(self.session, keyword=kw, species=species, active_only=False)

            sex_map = {"male": "Đực", "female": "Cái", "unknown": "Chưa rõ"}
            for p in pets:
                sex_text = sex_map.get(p["sex"], p["sex"])
                weight_text = f"{p['weight_kg']:.1f}" if p["weight_kg"] is not None else "-"
                status_text = "Đang theo dõi" if p["active"] else "Ngừng theo dõi"
                b_date = p["birth_date"] if p["birth_date"] else "-"

                self.table.insert_row(
                    (
                        p["id"],
                        p["name"],
                        p["species"],
                        p["breed"] or "-",
                        sex_text,
                        weight_text,
                        b_date,
                        p["owner_name"],
                        status_text,
                    ),
                    raw_data=p,
                )
        except Exception as e:
            show_error("Lỗi tải dữ liệu", str(e))

    def _show_add_dialog(self) -> None:
        self._open_form_dialog(title="Thêm thú cưng mới", existing=None)

    def _show_edit_dialog(self) -> None:
        selected = self.table.get_selected_data()
        if not selected:
            show_error("Thông báo", "Vui lòng chọn thú cưng cần sửa từ bảng danh sách")
            return
        self._open_form_dialog(title="Sửa thông tin thú cưng", existing=selected)

    def _open_form_dialog(self, title: str, existing: dict | None) -> None:
        # Tải danh sách chủ nuôi cho combobox
        try:
            owners = self.owner_service.list_owners(self.session, active_only=True)
            if not owners:
                show_error("Chưa có chủ nuôi", "Vui lòng thêm ít nhất một chủ nuôi trước khi thêm thú cưng")
                return
        except Exception as e:
            show_error("Lỗi", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.geometry("480x520")
        dlg.transient(self)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=20)
        frame.pack(fill="both", expand=True)

        # Chọn chủ nuôi
        ttk.Label(frame, text="Chủ nuôi:").pack(anchor="w", pady=(0, 2))
        owner_options = [f"{o['id']}: {o['full_name']} ({o['phone']})" for o in owners]
        cbo_owner = ttk.Combobox(frame, values=owner_options, state="readonly")
        cbo_owner.pack(fill="x", pady=(0, 8))

        # Chọn mặc định chủ nuôi
        if existing:
            for idx, opt in enumerate(owner_options):
                if opt.startswith(f"{existing['owner_id']}:"):
                    cbo_owner.current(idx)
                    break
        elif self.current_owner_filter:
            for idx, opt in enumerate(owner_options):
                if opt.startswith(f"{self.current_owner_filter}:"):
                    cbo_owner.current(idx)
                    break
        if not cbo_owner.get() and owner_options:
            cbo_owner.current(0)

        # Tên thú cưng
        ttk.Label(frame, text="Tên thú cưng:").pack(anchor="w", pady=(0, 2))
        ent_name = ttk.Entry(frame)
        ent_name.pack(fill="x", pady=(0, 8))

        # Loài & Giống
        row_sp = ttk.Frame(frame)
        row_sp.pack(fill="x", pady=(0, 8))

        col_sp = ttk.Frame(row_sp)
        col_sp.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Label(col_sp, text="Loài:").pack(anchor="w", pady=(0, 2))
        cbo_sp = ttk.Combobox(col_sp, values=["Chó", "Mèo", "Chim", "Chuột Hamster", "Khác"])
        cbo_sp.set("Chó")
        cbo_sp.pack(fill="x")

        col_br = ttk.Frame(row_sp)
        col_br.pack(side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Label(col_br, text="Giống (Breed):").pack(anchor="w", pady=(0, 2))
        ent_breed = ttk.Entry(col_br)
        ent_breed.pack(fill="x")

        # Giới tính & Cân nặng
        row_sex = ttk.Frame(frame)
        row_sex.pack(fill="x", pady=(0, 8))

        col_sex = ttk.Frame(row_sex)
        col_sex.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Label(col_sex, text="Giới tính:").pack(anchor="w", pady=(0, 2))
        cbo_sex = ttk.Combobox(col_sex, values=["Đực", "Cái", "Chưa rõ"], state="readonly")
        cbo_sex.set("Đực")
        cbo_sex.pack(fill="x")

        col_w = ttk.Frame(row_sex)
        col_w.pack(side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Label(col_w, text="Cân nặng (kg):").pack(anchor="w", pady=(0, 2))
        ent_weight = ttk.Entry(col_w)
        ent_weight.pack(fill="x")

        # Ngày sinh & Màu lông
        row_b = ttk.Frame(frame)
        row_b.pack(fill="x", pady=(0, 8))

        col_b = ttk.Frame(row_b)
        col_b.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Label(col_b, text="Ngày sinh (YYYY-MM-DD):").pack(anchor="w", pady=(0, 2))
        ent_birth = ttk.Entry(col_b)
        ent_birth.pack(fill="x")

        col_c = ttk.Frame(row_b)
        col_c.pack(side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Label(col_c, text="Màu lông:").pack(anchor="w", pady=(0, 2))
        ent_color = ttk.Entry(col_c)
        ent_color.pack(fill="x")

        var_active = tk.IntVar(value=1)
        if existing:
            ent_name.insert(0, existing["name"])
            cbo_sp.set(existing["species"])
            if existing["breed"]:
                ent_breed.insert(0, existing["breed"])
            sex_reverse = {"male": "Đực", "female": "Cái", "unknown": "Chưa rõ"}
            cbo_sex.set(sex_reverse.get(existing["sex"], "Chưa rõ"))
            if existing["weight_kg"] is not None:
                ent_weight.insert(0, str(existing["weight_kg"]))
            if existing["birth_date"]:
                ent_birth.insert(0, existing["birth_date"])
            if existing["coat_color"]:
                ent_color.insert(0, existing["coat_color"])
            var_active.set(existing["active"])
            ttk.Checkbutton(frame, text="Đang theo dõi (Active)", variable=var_active).pack(anchor="w", pady=(4, 12))

        def save():
            owner_val = cbo_owner.get()
            if not owner_val:
                show_error("Lỗi", "Vui lòng chọn chủ nuôi")
                return
            sel_owner_id = int(owner_val.split(":")[0])

            sex_forward = {"Đực": "male", "Cái": "female", "Chưa rõ": "unknown"}
            data = {
                "owner_id": sel_owner_id,
                "name": ent_name.get().strip(),
                "species": cbo_sp.get().strip(),
                "breed": ent_breed.get().strip(),
                "sex": sex_forward.get(cbo_sex.get(), "unknown"),
                "weight_kg": ent_weight.get().strip() or None,
                "birth_date": ent_birth.get().strip() or None,
                "coat_color": ent_color.get().strip(),
            }

            try:
                if existing:
                    data["active"] = var_active.get()
                    self.pet_service.update_pet(self.session, pet_id=existing["id"], data=data)
                    show_info("Thành công", "Đã cập nhật thông tin thú cưng thành công!")
                else:
                    self.pet_service.create_pet(self.session, data=data)
                    show_info("Thành công", "Đã thêm thú cưng mới thành công!")
                dlg.destroy()
                self.load_data()
            except Exception as e:
                show_error("Lỗi lưu dữ liệu", str(e))

        ttk.Button(frame, text="Lưu thông tin thú cưng", style="Primary.TButton", command=save).pack(fill="x", pady=(10, 0))

    def _delete_or_deactivate(self) -> None:
        selected = self.table.get_selected_data()
        if not selected:
            show_error("Thông báo", "Vui lòng chọn thú cưng từ bảng danh sách")
            return

        name = selected["name"]
        if not show_confirm(
            "Xác nhận",
            f"Bạn có muốn xóa hoặc ngừng theo dõi thú cưng '{name}'?\n"
            "(Nếu đã có hồ sơ y tế, lịch hẹn hoặc lượt dịch vụ, hệ thống sẽ tự động chuyển sang ngừng theo dõi)",
        ):
            return

        try:
            res = self.pet_service.delete_or_deactivate_pet(self.session, selected["id"])
            if res == "deleted":
                show_info("Đã xóa", f"Đã xóa hoàn toàn thú cưng '{name}'.")
            else:
                show_info("Đã ngừng theo dõi", f"Thú cưng '{name}' đã có dữ liệu lịch sử nên được chuyển sang trạng thái Ngừng theo dõi.")
            self.load_data()
        except Exception as e:
            show_error("Lỗi", str(e))

    def _view_profile(self) -> None:
        selected = self.table.get_selected_data()
        if not selected:
            show_error("Thông báo", "Vui lòng chọn thú cưng để xem hồ sơ")
            return
        if self.on_view_pet_profile:
            self.on_view_pet_profile(selected["id"])

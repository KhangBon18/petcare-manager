"""Dịch vụ quản lý hóa đơn và thanh toán trực tiếp."""

from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Any

from petcare.database.connection import get_connection, transaction
from petcare.repositories.invoice_repo import InvoiceRepository
from petcare.repositories.owner_repo import OwnerRepository
from petcare.repositories.visit_repo import VisitRepository
from petcare.services.auth_service import AuthSession


class InvoiceService:
    """Quy tắc nghiệp vụ hóa đơn, thanh toán và bảo toàn doanh thu."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        return get_connection(self.db_path)

    def _validate_session(self, session: AuthSession) -> None:
        if not session or not session.is_staff():
            raise PermissionError("Bạn cần đăng nhập để thao tác hóa đơn")

    def create_invoice(
        self,
        session: AuthSession,
        owner_id: int,
        visit_ids: list[int],
        note: str | None = None,
    ) -> int:
        """Tạo hóa đơn từ các lượt dịch vụ chưa thanh toán của cùng một chủ nuôi."""
        self._validate_session(session)

        if not owner_id:
            raise ValueError("Vui lòng chọn chủ nuôi để lập hóa đơn")

        if not visit_ids or len(visit_ids) == 0:
            raise ValueError("Hóa đơn phải có ít nhất một lượt dịch vụ")

        # Loại bỏ trùng lặp id trong danh sách truyền vào
        unique_visit_ids = list(dict.fromkeys(visit_ids))

        conn = self._get_connection()
        try:
            with transaction(conn):
                owner = OwnerRepository.get_by_id(conn, int(owner_id))
                if not owner:
                    raise ValueError("Chủ nuôi không tồn tại trong hệ thống")

                # Kiểm tra từng lượt dịch vụ
                visit_details: list[dict[str, Any]] = []
                for vid in unique_visit_ids:
                    visit = VisitRepository.get_by_id(conn, int(vid))
                    if not visit:
                        raise ValueError(f"Không tìm thấy lượt dịch vụ ID {vid}")

                    # Bắt buộc lượt dịch vụ phải thuộc về đúng chủ nuôi này
                    if visit["owner_id"] != int(owner_id):
                        raise ValueError(
                            f"Lượt dịch vụ ID {vid} ({visit['pet_name']}) không thuộc về chủ nuôi {owner['full_name']}"
                        )

                    # Bắt buộc lượt dịch vụ chưa được xuất hóa đơn nào khác
                    if InvoiceRepository.is_visit_billed(conn, int(vid)):
                        raise ValueError(f"Lượt dịch vụ ID {vid} đã được lập hóa đơn trước đó")

                    visit_details.append(visit)

                # 1. Tạo bản ghi hóa đơn header (status = 'unpaid')
                invoice_id = InvoiceRepository.create_invoice(
                    conn=conn,
                    owner_id=int(owner_id),
                    note=note,
                )

                # 2. Tạo các dòng chi tiết invoice_items với snapshot tên và giá
                for visit in visit_details:
                    InvoiceRepository.add_item(
                        conn=conn,
                        invoice_id=invoice_id,
                        visit_id=visit["id"],
                        service_name_snapshot=visit["service_name"],
                        pet_name_snapshot=visit["pet_name"],
                        amount_vnd=visit["unit_price_vnd"],
                    )

                return invoice_id
        finally:
            conn.close()

    def pay_invoice(self, session: AuthSession, invoice_id: int) -> str:
        """Thanh toán hóa đơn. Nếu đã thanh toán rồi thì trả về 'already_paid'."""
        self._validate_session(session)

        conn = self._get_connection()
        try:
            with transaction(conn):
                invoice = InvoiceRepository.get_by_id(conn, invoice_id)
                if not invoice:
                    raise ValueError("Không tìm thấy hóa đơn cần thanh toán")

                if invoice["status"] == "paid":
                    return "already_paid"

                if invoice["status"] == "cancelled":
                    raise ValueError("Không thể thanh toán hóa đơn đã bị hủy")

                now_str = datetime.now().isoformat()
                InvoiceRepository.mark_as_paid(conn, invoice_id, now_str)
                return "paid"
        finally:
            conn.close()

    def cancel_invoice(self, session: AuthSession, invoice_id: int) -> bool:
        """Hủy hóa đơn unpaid: giải phóng các lượt dịch vụ để lập hóa đơn khác. Chặn hủy hóa đơn paid."""
        self._validate_session(session)

        conn = self._get_connection()
        try:
            with transaction(conn):
                invoice = InvoiceRepository.get_by_id(conn, invoice_id)
                if not invoice:
                    raise ValueError("Không tìm thấy hóa đơn cần hủy")

                if invoice["status"] == "paid":
                    raise ValueError("Không thể hủy hóa đơn đã thanh toán thành công")

                if invoice["status"] == "cancelled":
                    return True

                return InvoiceRepository.cancel_invoice(conn, invoice_id)
        finally:
            conn.close()

    def get_invoice(self, session: AuthSession, invoice_id: int) -> dict[str, Any] | None:
        self._validate_session(session)
        conn = self._get_connection()
        try:
            return InvoiceRepository.get_by_id(conn, invoice_id)
        finally:
            conn.close()

    def list_invoices(
        self,
        session: AuthSession,
        status: str | None = None,
        owner_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        self._validate_session(session)
        conn = self._get_connection()
        try:
            return InvoiceRepository.list_all(conn, status=status, owner_id=owner_id, limit=limit)
        finally:
            conn.close()

"""Unit tests cho InvoiceService và InvoiceRepository."""

from pathlib import Path
import tempfile
import unittest

from petcare.database.initialize import initialize_database
from petcare.services.auth_service import AuthSession
from petcare.services.catalog_service import CatalogService
from petcare.services.exam_service import ExamService
from petcare.services.invoice_service import InvoiceService
from petcare.services.owner_service import OwnerService
from petcare.services.pet_service import PetService
from petcare.services.visit_service import VisitService


class TestInvoiceService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_invoice.db"
        initialize_database(self.db_path)

        self.admin_session = AuthSession(user_id=1, username="admin", role="admin", full_name="Admin")
        self.staff_session = AuthSession(user_id=2, username="staff", role="staff", full_name="Nhân viên")

        self.owner_service = OwnerService(self.db_path)
        self.pet_service = PetService(self.db_path)
        self.catalog_service = CatalogService(self.db_path)
        self.exam_service = ExamService(self.db_path)
        self.visit_service = VisitService(self.db_path)
        self.invoice_service = InvoiceService(self.db_path)

        # Chủ 1: Lan, Thú cưng: Miu & Lu
        self.owner_lan_id = self.owner_service.create_owner(
            self.staff_session,
            {"full_name": "Nguyễn Thị Lan", "phone": "0901234567", "address": "Quận 1"},
        )
        self.pet_miu_id = self.pet_service.create_pet(
            self.staff_session,
            {"owner_id": self.owner_lan_id, "name": "Miu", "species": "Mèo"},
        )
        self.pet_lu_id = self.pet_service.create_pet(
            self.staff_session,
            {"owner_id": self.owner_lan_id, "name": "Lu", "species": "Chó"},
        )

        # Chủ 2: Minh, Thú cưng: Bông
        self.owner_minh_id = self.owner_service.create_owner(
            self.staff_session,
            {"full_name": "Trần Văn Minh", "phone": "0912345678", "address": "Quận 3"},
        )
        self.pet_bong_id = self.pet_service.create_pet(
            self.staff_session,
            {"owner_id": self.owner_minh_id, "name": "Bông", "species": "Chó"},
        )

        # Dịch vụ
        self.svc_kham_id = self.catalog_service.create_service(
            self.admin_session,
            {"name": "Khám bệnh", "category": "Khám bệnh", "price_vnd": 150000},
        )
        self.svc_tam_id = self.catalog_service.create_service(
            self.admin_session,
            {"name": "Tắm spa", "category": "Chăm sóc", "price_vnd": 200000},
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_pay_invoice_success(self):
        # Miu khám bệnh
        _, visit_miu_kham = self.exam_service.record_exam(
            self.staff_session,
            {"pet_id": self.pet_miu_id, "service_id": self.svc_kham_id, "symptoms": "Sốt", "diagnosis": "Cảm"},
        )
        # Lu tắm spa
        visit_lu_tam = self.visit_service.record_service_usage(
            self.staff_session,
            pet_id=self.pet_lu_id,
            service_id=self.svc_tam_id,
        )

        # Lập hóa đơn gồm 2 lượt cho chị Lan
        inv_id = self.invoice_service.create_invoice(
            self.staff_session,
            owner_id=self.owner_lan_id,
            visit_ids=[visit_miu_kham, visit_lu_tam],
            note="Hóa đơn tổng hợp Lan",
        )
        self.assertIsInstance(inv_id, int)

        inv = self.invoice_service.get_invoice(self.staff_session, inv_id)
        self.assertEqual(inv["status"], "unpaid")
        self.assertEqual(len(inv["items"]), 2)
        self.assertEqual(inv["total_amount_vnd"], 350000)

        # Thanh toán
        pay_res = self.invoice_service.pay_invoice(self.staff_session, inv_id)
        self.assertEqual(pay_res, "paid")

        inv_paid = self.invoice_service.get_invoice(self.staff_session, inv_id)
        self.assertEqual(inv_paid["status"], "paid")
        self.assertIsNotNone(inv_paid["paid_at"])

        # Thanh toán lần 2 -> already_paid, không đổi paid_at
        pay_res_2 = self.invoice_service.pay_invoice(self.staff_session, inv_id)
        self.assertEqual(pay_res_2, "already_paid")

    def test_cannot_bill_different_owners_in_same_invoice(self):
        # Miu của Lan
        _, visit_miu = self.exam_service.record_exam(
            self.staff_session,
            {"pet_id": self.pet_miu_id, "service_id": self.svc_kham_id, "symptoms": "Sốt", "diagnosis": "Cảm"},
        )
        # Bông của Minh
        visit_bong = self.visit_service.record_service_usage(
            self.staff_session,
            pet_id=self.pet_bong_id,
            service_id=self.svc_tam_id,
        )

        # Cố tình gom lượt của Bông vào hóa đơn của Lan
        with self.assertRaises(ValueError):
            self.invoice_service.create_invoice(
                self.staff_session,
                owner_id=self.owner_lan_id,
                visit_ids=[visit_miu, visit_bong],
            )

    def test_cannot_bill_same_visit_twice(self):
        visit_id = self.visit_service.record_service_usage(
            self.staff_session,
            pet_id=self.pet_miu_id,
            service_id=self.svc_tam_id,
        )

        # Lập hóa đơn 1
        self.invoice_service.create_invoice(
            self.staff_session,
            owner_id=self.owner_lan_id,
            visit_ids=[visit_id],
        )

        # Cố tình lập lại lượt này vào hóa đơn 2
        with self.assertRaises(ValueError):
            self.invoice_service.create_invoice(
                self.staff_session,
                owner_id=self.owner_lan_id,
                visit_ids=[visit_id],
            )

    def test_cancel_unpaid_invoice_frees_visit(self):
        visit_id = self.visit_service.record_service_usage(
            self.staff_session,
            pet_id=self.pet_miu_id,
            service_id=self.svc_tam_id,
        )

        inv_id = self.invoice_service.create_invoice(
            self.staff_session,
            owner_id=self.owner_lan_id,
            visit_ids=[visit_id],
        )

        # Hủy hóa đơn unpaid
        success = self.invoice_service.cancel_invoice(self.staff_session, inv_id)
        self.assertTrue(success)

        inv = self.invoice_service.get_invoice(self.staff_session, inv_id)
        self.assertEqual(inv["status"], "cancelled")

        # Bây giờ visit_id đã được giải phóng, có thể lập hóa đơn mới
        inv_id_2 = self.invoice_service.create_invoice(
            self.staff_session,
            owner_id=self.owner_lan_id,
            visit_ids=[visit_id],
        )
        self.assertIsInstance(inv_id_2, int)

    def test_cannot_cancel_paid_invoice(self):
        visit_id = self.visit_service.record_service_usage(
            self.staff_session,
            pet_id=self.pet_miu_id,
            service_id=self.svc_tam_id,
        )
        inv_id = self.invoice_service.create_invoice(
            self.staff_session,
            owner_id=self.owner_lan_id,
            visit_ids=[visit_id],
        )
        self.invoice_service.pay_invoice(self.staff_session, inv_id)

        # Hóa đơn paid không được phép hủy
        with self.assertRaises(ValueError):
            self.invoice_service.cancel_invoice(self.staff_session, inv_id)


if __name__ == "__main__":
    unittest.main()

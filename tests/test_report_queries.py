"""Unit tests cho ReportService và ReportRepository."""

from datetime import date
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
from petcare.services.report_service import ReportService
from petcare.services.vaccination_service import VaccinationService
from petcare.services.visit_service import VisitService


class TestReportQueries(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_report.db"
        initialize_database(self.db_path)

        self.admin_session = AuthSession(user_id=1, username="admin", role="admin", full_name="Admin")
        self.staff_session = AuthSession(user_id=2, username="staff", role="staff", full_name="Nhân viên")

        self.owner_service = OwnerService(self.db_path)
        self.pet_service = PetService(self.db_path)
        self.catalog_service = CatalogService(self.db_path)
        self.exam_service = ExamService(self.db_path)
        self.vaccination_service = VaccinationService(self.db_path)
        self.visit_service = VisitService(self.db_path)
        self.invoice_service = InvoiceService(self.db_path)
        self.report_service = ReportService(self.db_path)

        # Tạo chủ và thú cưng
        self.owner_id = self.owner_service.create_owner(
            self.staff_session,
            {"full_name": "Nguyễn Thị Lan", "phone": "0901234567", "address": "Quận 1"},
        )
        self.pet_miu_id = self.pet_service.create_pet(
            self.staff_session,
            {"owner_id": self.owner_id, "name": "Miu", "species": "Mèo"},
        )
        self.pet_lu_id = self.pet_service.create_pet(
            self.staff_session,
            {"owner_id": self.owner_id, "name": "Lu", "species": "Chó"},
        )

        # Tạo dịch vụ
        self.svc_kham = self.catalog_service.create_service(
            self.admin_session,
            {"name": "Khám bệnh", "category": "Khám bệnh", "price_vnd": 100000},
        )
        self.svc_tiem = self.catalog_service.create_service(
            self.admin_session,
            {"name": "Tiêm Dại", "category": "Tiêm phòng", "price_vnd": 150000},
        )
        self.svc_tam = self.catalog_service.create_service(
            self.admin_session,
            {"name": "Tắm spa", "category": "Chăm sóc", "price_vnd": 200000},
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_report_summary_calculations(self):
        today_str = date.today().isoformat()

        # 1. Khám cho Miu (100k)
        _, v_kham = self.exam_service.record_exam(
            self.staff_session,
            {"pet_id": self.pet_miu_id, "service_id": self.svc_kham, "symptoms": "Sốt", "diagnosis": "Cảm"},
        )

        # 2. Tiêm cho Miu (150k)
        _, v_tiem = self.vaccination_service.record_vaccination(
            self.staff_session,
            {"pet_id": self.pet_miu_id, "service_id": self.svc_tiem, "vaccine_name": "Rabisin", "injection_date": today_str},
        )

        # 3. Tắm cho Lu (200k)
        v_tam = self.visit_service.record_service_usage(
            self.staff_session,
            pet_id=self.pet_lu_id,
            service_id=self.svc_tam,
        )

        # Hóa đơn 1 (paid): Khám Miu (100k) + Tiêm Miu (150k) = 250k
        inv_1 = self.invoice_service.create_invoice(
            self.staff_session,
            owner_id=self.owner_id,
            visit_ids=[v_kham, v_tiem],
        )
        self.invoice_service.pay_invoice(self.staff_session, inv_1)

        # Hóa đơn 2 (unpaid): Tắm Lu (200k) -> chưa thanh toán thì không được tính vào doanh thu
        self.invoice_service.create_invoice(
            self.staff_session,
            owner_id=self.owner_id,
            visit_ids=[v_tam],
        )

        # Lấy báo cáo cho ngày hôm nay
        report = self.report_service.get_summary(self.staff_session, start_date=today_str, end_date=today_str)

        # Doanh thu chỉ tính hóa đơn 1: 250.000 VND
        self.assertEqual(report["total_revenue_vnd"], 250000)
        self.assertEqual(report["paid_invoices_count"], 1)

        # Số lượt khám: 1
        self.assertEqual(report["exam_count"], 1)

        # Số thú cưng đã tiêm: 1 (mèo Miu)
        self.assertEqual(report["vaccinated_pets_count"], 1)

        # Phân bố loài: 1 Chó, 1 Mèo
        species_map = {item["species"]: item["count"] for item in report["species_distribution"]}
        self.assertEqual(species_map.get("Chó"), 1)
        self.assertEqual(species_map.get("Mèo"), 1)

        # Dịch vụ phổ biến trong các đơn paid
        svc_names = [s["service_name"] for s in report["popular_services"]]
        self.assertIn("Khám bệnh", svc_names)
        self.assertIn("Tiêm Dại", svc_names)
        self.assertNotIn("Tắm spa", svc_names, "Dịch vụ thuộc hóa đơn unpaid không được đưa vào thống kê paid")


if __name__ == "__main__":
    unittest.main()

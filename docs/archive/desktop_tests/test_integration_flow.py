"""Kiểm thử tích hợp luồng nghiệp vụ liên chức năng (End-to-End Integration Test).

Kịch bản:
Tạo chị Lan và mèo Miu -> ghi hẹn/khám/tiêm/tắm -> lập hóa đơn -> thanh toán -> xem lịch sử và thống kê.
"""

from datetime import date
from pathlib import Path
import tempfile
import unittest

from petcare.database.connection import get_connection
from petcare.database.initialize import initialize_database
from petcare.database.seed import seed_database
from petcare.services.appointment_service import AppointmentService
from petcare.services.auth_service import AuthService
from petcare.services.catalog_service import CatalogService
from petcare.services.exam_service import ExamService
from petcare.services.invoice_service import InvoiceService
from petcare.services.owner_service import OwnerService
from petcare.services.pet_service import PetService
from petcare.services.report_service import ReportService
from petcare.services.vaccination_service import VaccinationService
from petcare.services.visit_service import VisitService


class TestIntegrationFlow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_integration.db"
        initialize_database(self.db_path)

        # Khởi tạo các services
        self.auth_service = AuthService(self.db_path)
        self.owner_service = OwnerService(self.db_path)
        self.pet_service = PetService(self.db_path)
        self.catalog_service = CatalogService(self.db_path)
        self.exam_service = ExamService(self.db_path)
        self.vaccination_service = VaccinationService(self.db_path)
        self.visit_service = VisitService(self.db_path)
        self.appointment_service = AppointmentService(self.db_path)
        self.invoice_service = InvoiceService(self.db_path)
        self.report_service = ReportService(self.db_path)

        # Tạo sẵn tài khoản và dịch vụ cơ bản
        conn = get_connection(self.db_path)
        from petcare.security import hash_password
        pwd_hash, salt = hash_password("Staff@123")
        conn.execute(
            """
            INSERT INTO users (username, password_hash, salt, role, full_name, active, created_at)
            VALUES ('staff1', ?, ?, 'staff', 'Nhân viên Thử Nghiệm', 1, '2026-10-16T00:00:00')
            """,
            (pwd_hash, salt),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_complete_lan_and_miu_workflow(self):
        # 1. Đăng nhập Nhân viên
        session = self.auth_service.login("staff1", "Staff@123")
        self.assertTrue(session.is_staff())

        # Tạo các dịch vụ với giá niêm yết
        # Dùng admin session đăng nhập thực tế để tạo danh mục
        admin_session = self.auth_service.login("admin", "Admin@123")
        svc_kham_id = self.catalog_service.create_service(
            admin_session,
            {"name": "Khám lâm sàng", "category": "Khám bệnh", "price_vnd": 150000},
        )
        svc_tiem_id = self.catalog_service.create_service(
            admin_session,
            {"name": "Tiêm vaccine Dại", "category": "Tiêm phòng", "price_vnd": 180000},
        )
        svc_tam_id = self.catalog_service.create_service(
            admin_session,
            {"name": "Tắm vệ sinh cắt tỉa lông", "category": "Chăm sóc", "price_vnd": 200000},
        )

        # 2. Tạo chủ nuôi: Chị Lan
        owner_id = self.owner_service.create_owner(
            session,
            {
                "full_name": "Nguyễn Thị Lan",
                "phone": "0901234567",
                "address": "123 Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP.HCM",
            },
        )
        self.assertIsInstance(owner_id, int)

        # 3. Tạo thú cưng: Mèo Miu
        pet_id = self.pet_service.create_pet(
            session,
            {
                "owner_id": owner_id,
                "name": "Miu",
                "species": "Mèo",
                "breed": "Mèo Anh lông ngắn",
                "sex": "female",
                "birth_date": "2024-03-15",
                "weight_kg": 3.5,
                "coat_color": "Xám tro",
            },
        )
        self.assertIsInstance(pet_id, int)

        # 4. Ghi lịch hẹn: Khám & Tiêm phòng
        appt_id = self.appointment_service.create_appointment(
            session,
            {
                "pet_id": pet_id,
                "type": "Khám và tiêm phòng",
                "scheduled_at": "2026-10-16 09:00",
                "note": "Khách hàng hẹn khám tổng quát và tiêm nhắc vaccine",
            },
        )
        self.assertIsInstance(appt_id, int)

        # Xác nhận lịch hẹn chưa tạo bất kỳ khoản phí nào
        unbilled_initial = self.visit_service.get_unbilled_visits_by_owner(session, owner_id)
        self.assertEqual(len(unbilled_initial), 0, "Lịch hẹn không được tạo khoản phí")

        # 5. Ghi nhận ca khám bệnh cho Miu
        today_str = date.today().isoformat()
        exam_id, visit_exam_id = self.exam_service.record_exam(
            session,
            {
                "pet_id": pet_id,
                "service_id": svc_kham_id,
                "exam_date": today_str,
                "symptoms": "Hắt hơi nhẹ, ăn uống bình thường",
                "diagnosis": "Viêm đường hô hấp trên thể nhẹ",
                "medicines": "Thuốc nhỏ mắt mũi, men vi sinh 5 ngày",
            },
        )
        self.assertIsInstance(exam_id, int)
        self.assertIsInstance(visit_exam_id, int)

        # 6. Ghi nhận mũi tiêm vaccine cho Miu
        vac_id, visit_vac_id = self.vaccination_service.record_vaccination(
            session,
            {
                "pet_id": pet_id,
                "service_id": svc_tiem_id,
                "vaccine_name": "Rabisin (Vaccine Dại)",
                "injection_date": today_str,
                "next_due_date": "2027-10-16",
            },
        )
        self.assertIsInstance(vac_id, int)
        self.assertIsInstance(visit_vac_id, int)

        # 7. Ghi nhận dịch vụ tắm vệ sinh cho Miu
        visit_tam_id = self.visit_service.record_service_usage(
            session,
            pet_id=pet_id,
            service_id=svc_tam_id,
            performed_at=today_str,
            notes="Tắm spa và cắt móng gọn gàng",
        )
        self.assertIsInstance(visit_tam_id, int)

        # Cập nhật lịch hẹn thành hoàn thành (completed)
        self.appointment_service.update_status(session, appt_id, "completed")

        # 8. Kiểm tra danh sách lượt dịch vụ chưa thanh toán của chị Lan
        unbilled = self.visit_service.get_unbilled_visits_by_owner(session, owner_id)
        self.assertEqual(len(unbilled), 3, "Chị Lan phải có đúng 3 lượt dịch vụ chưa tính tiền")
        total_expected_vnd = 150000 + 180000 + 200000  # 530,000 VND
        self.assertEqual(sum(v["unit_price_vnd"] for v in unbilled), total_expected_vnd)

        # 9. Lập hóa đơn gồm cả 3 lượt dịch vụ
        invoice_id = self.invoice_service.create_invoice(
            session,
            owner_id=owner_id,
            visit_ids=[visit_exam_id, visit_vac_id, visit_tam_id],
            note="Thanh toán đợt khám và chăm sóc định kỳ cho Miu",
        )
        self.assertIsInstance(invoice_id, int)

        inv = self.invoice_service.get_invoice(session, invoice_id)
        self.assertEqual(inv["status"], "unpaid")
        self.assertEqual(inv["total_amount_vnd"], total_expected_vnd)
        self.assertEqual(len(inv["items"]), 3)

        # Lượt dịch vụ chưa thanh toán của chị Lan bây giờ là 0
        unbilled_after = self.visit_service.get_unbilled_visits_by_owner(session, owner_id)
        self.assertEqual(len(unbilled_after), 0)

        # Cố tính tiền lần hai cùng các lượt này phải bị từ chối
        with self.assertRaises(ValueError):
            self.invoice_service.create_invoice(
                session,
                owner_id=owner_id,
                visit_ids=[visit_exam_id],
            )

        # 10. Thanh toán trực tiếp tại quầy
        pay_result = self.invoice_service.pay_invoice(session, invoice_id)
        self.assertEqual(pay_result, "paid")

        inv_paid = self.invoice_service.get_invoice(session, invoice_id)
        self.assertEqual(inv_paid["status"], "paid")
        self.assertIsNotNone(inv_paid["paid_at"])

        # Thanh toán lần 2 trả về already_paid mà không đổi doanh thu
        pay_result_2 = self.invoice_service.pay_invoice(session, invoice_id)
        self.assertEqual(pay_result_2, "already_paid")

        # Hóa đơn đã thanh toán không được phép hủy
        with self.assertRaises(ValueError):
            self.invoice_service.cancel_invoice(session, invoice_id)

        # 11. Đối chiếu báo cáo thống kê
        summary = self.report_service.get_summary(session, start_date=today_str, end_date=today_str)
        self.assertEqual(summary["total_revenue_vnd"], total_expected_vnd)
        self.assertEqual(summary["paid_invoices_count"], 1)
        self.assertEqual(summary["exam_count"], 1)
        self.assertEqual(summary["vaccinated_pets_count"], 1)

        # Đối chiếu loài và top dịch vụ
        species_counts = {item["species"]: item["count"] for item in summary["species_distribution"]}
        self.assertEqual(species_counts.get("Mèo"), 1)

        popular_names = [item["service_name"] for item in summary["popular_services"]]
        self.assertIn("Khám lâm sàng", popular_names)
        self.assertIn("Tiêm vaccine Dại", popular_names)
        self.assertIn("Tắm vệ sinh cắt tỉa lông", popular_names)


if __name__ == "__main__":
    unittest.main()

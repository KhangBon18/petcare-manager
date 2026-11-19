import unittest

from petcare.i18n import translate, translate_audit_summary
from petcare.services.audit_service import ENTITY_LABELS, EVENT_LABELS


class AuditSummaryLocalizationTests(unittest.TestCase):
    def test_refund_summary_is_localized_with_amount_currency_and_invoice(self):
        self.assertEqual(
            translate_audit_summary("Hoàn 125000.50 VND cho hóa đơn #42", "en"),
            "Recorded a refund of 125000.50 VND for invoice #42",
        )

    def test_vietnamese_audit_summary_is_preserved(self):
        summary = "Hoàn 125000.50 VND cho hóa đơn #42"
        self.assertEqual(translate_audit_summary(summary, "vi"), summary)

    def test_historical_account_and_signup_summaries_are_translated(self):
        self.assertEqual(
            translate_audit_summary("Cập nhật tên hiển thị tài khoản", "en"),
            "Updated account display name",
        )
        self.assertEqual(
            translate_audit_summary("Bắt đầu đăng ký cửa hàng tự phục vụ", "en"),
            "Started self-service store signup",
        )

    def test_audit_event_and_entity_labels_cover_new_workflows(self):
        self.assertEqual(EVENT_LABELS["invoice.refunded"], "Hoàn tiền hóa đơn")
        self.assertEqual(EVENT_LABELS["account.profile_updated"], "Cập nhật tên tài khoản")
        self.assertEqual(translate("invoice.refunded", "en"), "Recorded invoice refund")
        self.assertEqual(translate("purchase_order", "en"), "Purchase order")
        self.assertEqual(translate("supplier", "en"), "Supplier")
        self.assertEqual(translate("invoice_refund", "en"), "Invoice refund")
        self.assertIn("invoice_refund", ENTITY_LABELS)
        for code in EVENT_LABELS:
            with self.subTest(event_type=code):
                self.assertNotEqual(translate(code, "en"), code)
        for code in ENTITY_LABELS:
            with self.subTest(entity_type=code):
                self.assertNotEqual(translate(code, "en"), code)

    def test_remaining_dynamic_workflow_errors_are_translated(self):
        cases = {
            "Bạn đã thử bàn giao quá nhiều lần. Vui lòng thử lại sau.":
                "Too many ownership transfer attempts. Please try again later.",
            "Bản báo cáo đã hết hạn hoặc không hợp lệ. Tải lại báo cáo rồi xuất lại.":
                "This report snapshot expired or is invalid. Reload the report and export it again.",
            "Kỳ có hơn 5.000 dòng hàng; hãy chọn khoảng ngày ngắn hơn để xuất đầy đủ.":
                "This period has more than 5,000 line items. Choose a shorter date range to export all details.",
            "Danh sách hàng nhận không hợp lệ.": "The received-item list is invalid.",
            "Tên hiển thị không được dài quá 160 ký tự.": "The display name must be 160 characters or fewer.",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(translate(source, "en"), expected)


if __name__ == "__main__":
    unittest.main()

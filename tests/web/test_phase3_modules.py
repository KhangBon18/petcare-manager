from copy import deepcopy
from datetime import date
from decimal import Decimal
from io import BytesIO
import html
import re
from unittest import TestCase
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from petcare import create_app
from petcare.services import report_export_service


def report_data():
    return {
        "start_date": date(2026, 10, 25),
        "end_date": date(2026, 10, 25),
        "captured_at": "2026-10-25T10:00:00+07:00",
        "tenant_name": "Demo",
        "timezone": "Asia/Ho_Chi_Minh",
        "currency_code": "VND",
        "summary": {"revenue": Decimal(100000), "invoice_count": 1},
        "previous": {"revenue": Decimal(50000), "invoice_count": 1},
        "previous_start": date(2026, 10, 24),
        "previous_end": date(2026, 10, 24),
        "growth": Decimal(100),
        "inventory": {"units_in_stock": 5, "low_stock_count": 1},
        "pets_sold": {"pets_sold": 0},
        "peak": {"date": "2026-10-25", "revenue": Decimal(100000)},
        "chart_bars": [],
        "brief": ["Doanh thu tăng 100%."],
        "top_products": [],
        "daily": [
            {"date": "2026-10-25", "revenue": Decimal(100000), "invoice_count": 1}
        ],
        "details": [
            {
                "invoice_id": 1,
                "paid_at": "2026-10-25T09:00:00+07:00",
                "entry_type": "sale",
                "item_type": "product",
                "code": "P1",
                "name": "Food",
                "quantity": 1,
                "unit_price": Decimal(100000),
                "line_total": Decimal(100000),
            }
        ],
    }


class PhaseThreeWebTests(TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "phase3-web-secret",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()
        self.user = {
            "id": 1,
            "role": "admin",
            "full_name": "Demo",
            "preferred_locale": "vi",
            "store_memberships": [],
            "tenant": {
                "id": 1,
                "slug": "main",
                "name": "Demo",
                "default_currency": "VND",
                "timezone": "Asia/Ho_Chi_Minh",
            },
        }
        with self.client.session_transaction() as session:
            session.update(user_id=1, tenant_id=1, session_version=0, locale="vi")
        self.patch(
            "petcare.auth.load_active_user", side_effect=lambda *a: deepcopy(self.user)
        )
        self.patch(
            "petcare.services.request_throttle_service.consume_with_ip_limit",
            return_value=(True, 0),
        )

    def patch(self, target, **kwargs):
        p = patch(target, **kwargs)
        self.addCleanup(p.stop)
        return p.start()

    def test_assistant_cards_use_trusted_routes_and_formatted_decimal(self):
        self.patch(
            "petcare.routes.assistant_routes.assistant_service.answer",
            return_value={
                "reply": "Một kết quả",
                "mode": "local",
                "currency_code": "VND",
                "catalog": {
                    "total": 301,
                    "items": [
                        {
                            "id": 901,
                            "kind": "pet",
                            "name": "<Miu>",
                            "code": "PET-901",
                            "price": "2999999",
                            "status": "available",
                            "stock": 1,
                            "photo_filename": "t1-photo.jpg",
                        }
                    ],
                },
            },
        )
        response = self.client.post(
            "/assistant/chat", json={"message": "mèo trắng dưới 3 triệu"}
        )
        self.assertEqual(response.status_code, 200)
        result = response.get_json()["catalog"]
        item = result["items"][0]
        self.assertEqual(result["total"], 301)
        self.assertEqual(item["url"], "/pets/901")
        self.assertEqual(item["photo_url"], "/pets/photo/t1-photo.jpg")
        self.assertEqual(item["price_label"], "2.999.999\u00a0VND")
        self.assertNotIn("photo_filename", item)

    def test_report_print_and_xlsx_export_share_signed_screen_snapshot(self):
        self.patch(
            "petcare.routes.report_routes.report_service.report",
            return_value=report_data(),
        )
        response = self.client.get("/reports/?period=7d")
        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("data-print-report", page)
        self.assertIn("Doanh thu tăng 100%", page)
        token = html.unescape(
            re.search(r'name="snapshot" value="([^"]+)"', page).group(1)
        )
        result = self.client.post("/reports/export.xlsx", json={"snapshot": token})
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.data.startswith(b"PK"))
        self.assertIn("attachment", result.headers["Content-Disposition"])
        self.assertNotIn('style="', page)

    def test_english_report_export_uses_the_current_ui_locale(self):
        self.patch(
            "petcare.routes.report_routes.report_service.report",
            return_value=report_data(),
        )
        self.user["preferred_locale"] = "en"
        with self.client.session_transaction() as session:
            session["locale"] = "en"
        page = self.client.get("/reports/?period=7d")
        self.assertEqual(page.status_code, 200)
        page_html = page.get_data(as_text=True)
        self.assertIn("BUSINESS BRIEF", page_html)
        self.assertIn("Snapshot at Oct 25, 2026 10:00 AM", page_html)
        self.assertIn("Oct 25, 2026 9:00 AM", page_html)
        self.assertIn("Oct 25, 2026", page_html)
        token = html.unescape(
            re.search(r'name="snapshot" value="([^"]+)"', page.get_data(as_text=True)).group(1)
        )
        result = self.client.post("/reports/export.xlsx", json={"snapshot": token})
        self.assertEqual(result.status_code, 200)
        with ZipFile(BytesIO(result.data)) as workbook:
            strings = workbook.read("xl/sharedStrings.xml").decode()
            root = ET.fromstring(workbook.read("xl/workbook.xml"))
        self.assertIn("Paid revenue", strings)
        self.assertIn("SALES AND REFUNDS", strings)
        names = [
            sheet.attrib["name"]
            for sheet in root.findall(
                ".//m:sheet",
                {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"},
            )
        ]
        self.assertEqual(names, ["Overview", "Daily revenue", "Details", "Top products"])

    def test_english_report_validation_error_is_translated(self):
        from petcare.services.exceptions import ValidationError

        self.user["preferred_locale"] = "en"
        self.patch(
            "petcare.routes.report_routes.report_service.report",
            side_effect=ValidationError("Ngày bắt đầu không được sau ngày kết thúc."),
        )
        response = self.client.get("/reports/?start=2026-10-25&end=2026-10-24")
        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 400)
        self.assertIn("The start date cannot be after the end date.", page)
        self.assertNotIn("Ngày bắt đầu không được sau ngày kết thúc.", page)

    def test_english_assistant_api_error_is_translated(self):
        from petcare.services.exceptions import ValidationError

        self.user["preferred_locale"] = "en"
        self.patch(
            "petcare.routes.assistant_routes.assistant_service.answer",
            side_effect=ValidationError("Nội dung gửi lên chưa hợp lệ."),
        )
        response = self.client.post("/assistant/chat", json={"message": "hello"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"], "The submitted message is invalid."
        )

    def test_export_rejects_wrong_user_or_tenant_bad_signature_and_payloads(self):
        with self.app.app_context():
            token = report_export_service.snapshot(report_data(), 2, 1)
        for payload in (
            {"snapshot": token},
            {"snapshot": "tampered"},
            [],
            {"snapshot": 12},
            None,
        ):
            self.assertEqual(
                self.client.post("/reports/export.xlsx", json=payload).status_code, 400
            )

    def test_export_and_attribute_suggestion_require_login_and_csrf(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        self.assertEqual(
            self.client.post(
                "/reports/export.xlsx", json={"snapshot": "x"}
            ).status_code,
            400,
        )
        self.assertEqual(self.client.post("/pets/suggest-attributes").status_code, 400)
        self.app.config["WTF_CSRF_ENABLED"] = False
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.post("/reports/export.xlsx").status_code, 302)

    def test_attribute_suggestion_is_admin_only_with_useful_json(self):
        service = self.patch(
            "petcare.routes.pet_routes.pet_image_service.suggest_attributes",
            return_value={
                "suggestions": {"coat_color": "trắng"},
                "colors": ["trắng"],
                "mode": "local",
                "warning": None,
            },
        )
        result = self.client.post(
            "/pets/suggest-attributes", data={"photo": (BytesIO(b"image"), "a.jpg")}
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()["mode"], "local")
        service.assert_called_once()
        self.user["role"] = "staff"
        result = self.client.post(
            "/pets/suggest-attributes", data={"photo": (BytesIO(b"image"), "a.jpg")}
        )
        self.assertEqual(result.status_code, 403)

    def test_attribute_suggestion_handles_rate_limit_missing_file_and_busy_slot(self):
        self.assertEqual(self.client.post("/pets/suggest-attributes").status_code, 400)
        self.patch(
            "petcare.services.request_throttle_service.consume_with_ip_limit",
            return_value=(False, 3),
        )
        self.assertEqual(self.client.post("/pets/suggest-attributes").status_code, 429)
        slots = self.app.extensions["petcare_image_processing_slots"]
        taken = []
        while slots.acquire(blocking=False):
            taken.append(1)
        try:
            result = self.client.post(
                "/pets/suggest-attributes", data={"photo": (BytesIO(b"image"), "a.jpg")}
            )
            self.assertEqual(result.status_code, 429)
            self.assertIsNotNone(result.get_json())
            self.assertEqual(result.headers["Retry-After"], "2")
        finally:
            for _ in taken:
                slots.release()

    def test_image_filters_forwarded_and_explanations_render_without_inline_styles(
        self,
    ):
        service = self.patch(
            "petcare.routes.pet_routes.pet_image_service.search_similar",
            return_value={
                "has_reference_photos": True,
                "dominant_colors": ["trắng"],
                "analysis": None,
                "warning": None,
                "search_scope": "full",
                "results": [
                    {
                        "pet": {
                            "id": 1,
                            "code": "PET1",
                            "name": "Miu",
                            "species": "Mèo",
                            "breed": "",
                            "coat_color": "trắng",
                            "eye_color": "xanh",
                            "sale_price": Decimal(10),
                            "photo_filename": None,
                            "sale_status": "sold",
                        },
                        "score": 90,
                        "components": {"color": 95, "structure": 85, "attributes": 70},
                    }
                ],
            },
        )
        result = self.client.post(
            "/pets/find-similar",
            data={
                "species": "Mèo",
                "status": "sold",
                "photo": (BytesIO(b"photo"), "a.jpg"),
            },
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(service.call_args.kwargs, {"species": "Mèo", "status": "sold"})
        page = result.get_data(as_text=True)
        self.assertIn("Màu sắc 95/100", page)
        self.assertIn("Cấu trúc 85/100", page)
        self.assertNotIn('style="', page)

    def test_product_profile_is_readable_by_staff_and_restock_shows_formula(self):
        self.user["role"] = "staff"
        self.patch(
            "petcare.routes.product_routes.product_service.get_product",
            return_value={
                "id": 1,
                "code": "P1",
                "name": "Food",
                "active": True,
                "category": "Thức ăn",
                "unit_price": Decimal(10),
                "description": "",
                "stock_qty": 1,
                "photo_filename": None,
            },
        )
        from petcare.services.restock_service import estimate

        item = estimate(
            {
                "id": 1,
                "code": "P1",
                "name": "Food",
                "stock_qty": 1,
                "reorder_level": 2,
                "sold_14": 14,
                "sold_30": 30,
            }
        )
        self.patch(
            "petcare.routes.product_routes.restock_service.recommendations",
            return_value=[item],
        )
        result = self.client.get("/products/1")
        self.assertEqual(result.status_code, 200)
        self.assertIn("ceil(", result.get_data(as_text=True))
        self.assertNotIn("/products/1/edit", result.get_data(as_text=True))

    def test_oversized_or_invalid_report_period_is_recoverable_without_fake_totals(
        self,
    ):
        from petcare.services.exceptions import ValidationError

        service = self.patch(
            "petcare.routes.report_routes.report_service.report",
            side_effect=ValidationError("Chọn kỳ ngắn hơn."),
        )
        response = self.client.get("/reports/?start=2020-01-01&end=2026-10-25")
        self.assertEqual(response.status_code, 400)
        page = response.get_data(as_text=True)
        self.assertIn('value="2020-01-01"', page)
        self.assertIn('role="alert"', page)
        self.assertNotIn("data-report-export", page)
        self.assertNotIn("0 VND", page)
        service.assert_called_once()

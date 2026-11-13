from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import json
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from flask import Flask
from PIL import Image

from petcare.ai.client import AIProviderError
from petcare.repositories import catalog_repo
from petcare.services import (
    assistant_service,
    catalog_service,
    pet_image_service,
    report_service,
    report_export_service,
    restock_service,
)
from petcare.services.exceptions import ValidationError
from petcare.vision.image_features import describe_image, similarity_components


def report_fixture():
    return {
        "tenant_name": "Demo",
        "currency_code": "VND",
        "timezone": "Asia/Ho_Chi_Minh",
        "start_date": date(2026, 10, 24),
        "end_date": date(2026, 10, 25),
        "captured_at": "2026-10-25T12:00:00+07:00",
        "summary": {"revenue": Decimal("150000"), "invoice_count": 1},
        "previous": {"revenue": Decimal("100000"), "invoice_count": 1},
        "growth": Decimal("50"),
        "pets_sold": {"pets_sold": 0},
        "inventory": {"units_in_stock": 10},
        "brief": ["Một giao dịch đã thu."],
        "daily": [
            {"date": "2026-10-24", "revenue": Decimal(0), "invoice_count": 0},
            {"date": "2026-10-25", "revenue": Decimal("150000"), "invoice_count": 1},
        ],
        "details": [
            {
                "invoice_id": 1,
                "paid_at": "2026-10-25T12:00:00+07:00",
                "entry_type": "sale",
                "item_type": "product",
                "code": "P1",
                "name": '=WEBSERVICE("https://example.test")',
                "quantity": 3,
                "unit_price": Decimal("50000"),
                "line_total": Decimal("150000"),
            }
        ],
        "chart_bars": [],
    }


def cells_from_xlsx(blob, sheet=1):
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(BytesIO(blob)) as book:
        strings = [
            "".join(n.itertext())
            for n in ET.fromstring(book.read("xl/sharedStrings.xml")).findall(
                "m:si", ns
            )
        ]
        root = ET.fromstring(book.read(f"xl/worksheets/sheet{sheet}.xml"))
        values = {}
        for cell in root.findall(".//m:c", ns):
            node = cell.find("m:v", ns)
            if node is not None:
                values[cell.attrib["r"]] = (
                    strings[int(node.text)]
                    if cell.get("t") == "s"
                    else Decimal(node.text)
                )
        return values, root


class CatalogSQLTests(unittest.TestCase):
    def test_traits_price_and_hostile_text_are_parameters_not_sql(self):
        spec = assistant_service.pet_filter_spec(
            "Hôm nay tìm mèo lông trắng dưới 3 triệu"
        )
        self.assertEqual(spec["species"], "cat")
        self.assertEqual(spec["terms"], [])
        spec["terms"] = ["x%' OR 1=1 --"]
        with patch.object(
            catalog_repo, "fetch_one", return_value={"total": 401}
        ) as count, patch.object(catalog_repo, "fetch_all", return_value=[]) as rows:
            total, items = catalog_repo.search(object(), "pet", spec)
        self.assertEqual(total, 401)
        self.assertEqual(items, [])
        sql, params = count.call_args.args[1:]
        self.assertIn("tenant_id = @petcare_tenant_id", sql)
        self.assertIn("sale_price < %s", sql)
        self.assertNotIn("OR 1=1", sql)
        self.assertTrue(any("OR 1==1" in str(p) for p in params))
        self.assertNotIn("LIMIT", sql)
        self.assertEqual(rows.call_args.args[2][-1], 12)
        self.assertIn(Decimal("3000000"), params)

    def test_lookup_preserves_exact_count_decimal_and_server_record_id(self):
        with patch.object(
            catalog_repo,
            "search",
            return_value=(
                251,
                [
                    {
                        "id": 900,
                        "code": "PET-900",
                        "name": "Sữa",
                        "sale_price": Decimal("2999999"),
                        "sale_status": "available",
                        "photo_filename": "photo.jpg",
                    }
                ],
            ),
        ):
            result = catalog_service.lookup(object(), "mèo trắng dưới 3 triệu", "pet")
        self.assertEqual(result["total"], 251)
        self.assertEqual(result["items"][0]["price"], "2999999")
        self.assertEqual(result["items"][0]["id"], 900)

    def test_invalid_catalog_never_reaches_database(self):
        with self.assertRaises(ValueError):
            catalog_repo.search(None, "pets; DROP TABLE users", {})

    def test_pet_code_and_specific_breed_survive_parsing(self):
        self.assertIn(
            "pet-999", assistant_service.pet_filter_spec("Tìm PET-999")["terms"]
        )
        self.assertIn(
            "husky",
            assistant_service.pet_filter_spec("Có chó giống Husky dưới 20 triệu?")[
                "terms"
            ],
        )


class AssistantFallbackTests(unittest.TestCase):
    def test_cards_are_identical_offline_online_and_when_provider_fails(self):
        app = Flask(__name__)
        result = {
            "kind": "pet",
            "total": 301,
            "items": [
                {
                    "id": 901,
                    "name": "Mây",
                    "code": "PET-901",
                    "price": "2700000",
                    "stock": 1,
                    "status": "available",
                }
            ],
        }

        @contextmanager
        def connection():
            yield object()

        for configured, failure in ((False, False), (True, False), (True, True)):
            with self.subTest(
                configured=configured, failure=failure
            ), app.app_context(), patch.object(
                assistant_service, "read_connection", connection
            ), patch.object(
                assistant_service,
                "require_actor",
                return_value={
                    "timezone": "Asia/Ho_Chi_Minh",
                    "default_currency": "VND",
                },
            ), patch.object(
                assistant_service.assistant_repo, "shop_context", return_value={}
            ), patch.object(
                catalog_service, "lookup", return_value=result
            ), patch.object(
                assistant_service.ai_client, "is_configured", return_value=configured
            ), patch.object(
                assistant_service.ai_client,
                "complete",
                side_effect=AIProviderError("offline") if failure else None,
                return_value="Có kết quả.",
            ) as complete:
                answer = assistant_service.answer(
                    1, "mèo trắng dưới 3 triệu", locale="vi"
                )
                self.assertEqual(answer["catalog"], result)
                self.assertEqual(
                    answer["mode"], "ai" if configured and not failure else "local"
                )
                if not configured:
                    complete.assert_not_called()


class RestockTests(unittest.TestCase):
    def test_sales_query_uses_paid_invoices_and_bound_half_open_dates(self):
        from petcare.repositories import restock_repo

        windows = tuple(
            (f"week{index}-start", f"week{index}-end") for index in range(8)
        )
        with patch.object(restock_repo, "fetch_all", return_value=[]) as fetch:
            restock_repo.sales_inventory(
                object(), "start30", "start14", "end", "history-start", windows
            )
        sql, params = fetch.call_args.args[1:]
        self.assertIn("i.status = 'paid'", sql)
        self.assertIn("ii.item_type = 'product'", sql)
        self.assertIn("i.paid_at >= %s AND i.paid_at < %s", sql)
        self.assertIn("iri.disposition <> 'not_returned'", sql)
        self.assertIn("po.status IN ('ordered', 'partially_received')", sql)
        self.assertIn("poi.tenant_id = @petcare_tenant_id", sql)
        self.assertEqual(
            params,
            (
                "start14", "start30",
                *(value for window in windows for value in window),
                "history-start", "end", "history-start", "end",
            ),
        )
        self.assertEqual(sql, restock_repo.SALES_INVENTORY_SQL)

    def test_sales_query_requires_the_fixed_forecast_window_count(self):
        from petcare.repositories import restock_repo

        with self.assertRaisesRegex(ValueError, "eight weekly windows"):
            restock_repo.sales_inventory(object(), "30", "14", "end")

    def row(self, **kw):
        return dict(
            id=1,
            name="Food",
            stock_qty=3,
            reorder_level=2,
            sold_14=28,
            sold_30=30,
            **kw,
        )

    def test_paid_velocity_and_ceil_target(self):
        result = restock_service.estimate(self.row())
        self.assertEqual(result["rate_14"], 2)
        self.assertEqual(result["rate_30"], 1)
        self.assertEqual(result["days_left"], Decimal("1.5"))
        self.assertEqual(result["suggested_qty"], 25)
        self.assertTrue(result["warning"])
        self.assertEqual(result["window"], 14)

    def test_30_day_fallback_when_no_recent_sales(self):
        row = self.row()
        row.update(sold_14=0, sold_30=15)
        result = restock_service.estimate(row)
        self.assertEqual(result["window"], 30)
        self.assertEqual(result["days_left"], 6)
        self.assertEqual(result["suggested_qty"], 4)

    def test_new_product_uses_reorder_level_without_division_by_zero(self):
        row = self.row()
        row.update(sold_14=0, sold_30=0, stock_qty=0)
        result = restock_service.estimate(row)
        self.assertIsNone(result["days_left"])
        self.assertEqual(result["basis"], "reorder_level")
        self.assertTrue(result["warning"])
        self.assertEqual(result["suggested_qty"], 3)

    def test_integer_ceiling_does_not_add_stock_due_to_repeating_decimal_roundoff(self):
        row = self.row()
        row.update(stock_qty=0, reorder_level=0, sold_14=5, sold_30=9)
        result = restock_service.estimate(row)
        self.assertEqual(result["target"], 5)
        self.assertEqual(result["suggested_qty"], 5)

    def test_adequate_stock_never_suggests_negative_order(self):
        row = self.row()
        row["stock_qty"] = 100
        result = restock_service.estimate(row)
        self.assertEqual(result["suggested_qty"], 0)
        self.assertFalse(result["warning"])


class ReportAutomationTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["SECRET_KEY"] = "phase3-unit-report-secret"

    def test_dashboard_keeps_exact_headlines_when_chart_period_exceeds_detail_limit(
        self,
    ):
        @contextmanager
        def connection():
            yield object()

        actor = {"timezone": "Asia/Ho_Chi_Minh", "default_currency": "VND"}
        with self.app.app_context(), patch.object(
            report_service, "read_connection", connection
        ), patch.object(
            report_service, "require_actor", return_value=actor
        ), patch.object(
            report_service.report_repo,
            "dashboard",
            return_value={"today": Decimal(100)},
        ), patch.object(
            report_service.report_repo,
            "summary",
            return_value={"revenue": Decimal(900)},
        ), patch.object(
            report_service.restock_service, "for_connection", return_value=[]
        ), patch.object(
            report_service,
            "_report",
            side_effect=ValidationError("Choose a shorter period."),
        ):
            metrics = report_service.dashboard(1)
        self.assertEqual(metrics["today"], 100)
        self.assertEqual(metrics["last_seven_days"], 900)
        self.assertIn("business_error", metrics)
        self.assertNotIn("business", metrics)

    def test_snapshot_scoped_tamper_and_expiry(self):
        with self.app.app_context():
            with patch("itsdangerous.timed.time.time", return_value=1000):
                token = report_export_service.snapshot(report_fixture(), 1, 2)
            with patch("itsdangerous.timed.time.time", return_value=1001):
                result = report_export_service.read_snapshot(token, 1, 2)
                self.assertEqual(result["summary"]["revenue"], "150000")
                for actor, tenant in ((2, 2), (1, 3)):
                    with self.assertRaises(ValidationError):
                        report_export_service.read_snapshot(token, actor, tenant)
                with self.assertRaises(ValidationError):
                    report_export_service.read_snapshot(token + "x", 1, 2)
            with patch("itsdangerous.timed.time.time", return_value=2000):
                with self.assertRaises(ValidationError):
                    report_export_service.read_snapshot(token, 1, 2)

    def test_xlsx_reconciles_overview_daily_and_line_details_and_does_not_execute_text(
        self,
    ):
        blob = report_export_service.workbook_bytes(
            json.loads(json.dumps(report_fixture(), default=str))
        )
        overview, _ = cells_from_xlsx(blob, 1)
        daily, _ = cells_from_xlsx(blob, 2)
        details, root = cells_from_xlsx(blob, 3)
        self.assertEqual(overview["B6"], 150000)
        self.assertEqual(daily["B6"] + daily["B7"], overview["B6"])
        self.assertEqual(details["I6"], overview["B6"])
        self.assertEqual(details["I7"], overview["B6"])
        self.assertTrue(details["F6"].startswith("=WEBSERVICE"))
        self.assertNotIn(b"<f>", ET.tostring(root))
        with ZipFile(BytesIO(blob)) as book:
            self.assertIn("₫", book.read("xl/styles.xml").decode())
            self.assertIn("frozen", book.read("xl/worksheets/sheet3.xml").decode())

    def test_english_xlsx_localizes_labels_dates_and_report_summary(self):
        blob = report_export_service.workbook_bytes(
            json.loads(json.dumps(report_fixture(), default=str)), locale="en"
        )
        overview, _ = cells_from_xlsx(blob, 1)
        with ZipFile(BytesIO(blob)) as book:
            workbook = ET.fromstring(book.read("xl/workbook.xml"))
            names = [node.attrib["name"] for node in workbook.findall(".//m:sheet", {
                "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
            })]
            strings = book.read("xl/sharedStrings.xml").decode()
        self.assertEqual(names, ["Overview", "Daily revenue", "Details", "Top products"])
        self.assertIn("Paid revenue", strings)
        self.assertIn("SALES AND REFUNDS", strings)
        self.assertIn("Paid invoices", strings)
        self.assertNotIn("Doanh thu đã thu", strings)
        self.assertIn("Revenue changed by", strings)
        self.assertEqual(overview["B6"], 150000)

    def test_large_amount_is_exact_text_not_silently_rounded_by_excel(self):
        report = report_fixture()
        report["summary"]["revenue"] = Decimal("9999999999999999")
        values, _ = cells_from_xlsx(report_export_service.workbook_bytes(report))
        self.assertEqual(values["B6"], "9999999999999999 VND")

    def test_zero_previous_revenue_does_not_invent_growth(self):
        report = report_fixture()
        report.update(growth=None, peak={"date": "2026-10-25"})
        self.assertIn("nền bằng 0", report_service.business_brief(report)[1])

    def test_business_brief_uses_locale_number_and_date_formats(self):
        report = report_fixture()
        report["summary"]["invoice_count"] = 1234
        report["growth"] = Decimal("1234.56")
        report["peak"] = {"date": "2026-10-25"}
        report["top_products"] = [{"name": "Food", "quantity_sold": 12345}]

        english = report_service.business_brief(report, "en")
        self.assertIn("1,234 paid invoices", english[0])
        self.assertIn("+1,234.6%", english[1])
        self.assertEqual(english[2], "Best day: Oct 25, 2026.")
        self.assertIn("Food (12,345)", english[3])

        vietnamese = report_service.business_brief(report, "vi")
        self.assertIn("1.234 hóa đơn", vietnamese[0])
        self.assertIn("+1.234,6%", vietnamese[1])
        self.assertEqual(vietnamese[2], "Ngày doanh thu cao nhất: 25/10/2026.")
        self.assertIn("Food (12.345)", vietnamese[3])

    def test_period_bounds_reject_unbounded_range(self):
        with self.assertRaises(ValidationError):
            report_service._period("2020-01-01", "2026-10-25", "Asia/Ho_Chi_Minh")

    def test_daily_local_dates_zero_fill_previous_equal_length_and_paid_lines_reconcile(
        self,
    ):
        actor = {
            "timezone": "America/Los_Angeles",
            "default_currency": "VND",
            "tenant_name": "Demo",
        }
        rows = [
            {
                "invoice_id": 1,
                "paid_at": datetime(2026, 3, 8, 9, 30),
                "entry_type": "sale",
                "line_total": Decimal(20),
            },
            {
                "invoice_id": 1,
                "paid_at": datetime(2026, 3, 8, 9, 30),
                "entry_type": "sale",
                "line_total": Decimal(30),
            },
        ]
        with self.app.app_context(), patch.object(
            report_service.report_repo, "paid_lines", return_value=rows
        ), patch.object(
            report_service.report_repo,
            "summary",
            return_value={"revenue": Decimal(25), "invoice_count": 1},
        ) as prev, patch.object(
            report_service.report_repo, "top_products", return_value=[]
        ), patch.object(
            report_service.report_repo, "inventory", return_value={}
        ), patch.object(
            report_service.report_repo, "pets_sold", return_value={}
        ):
            result = report_service._report(object(), actor, "2026-03-08", "2026-03-09")
        self.assertEqual(result["summary"]["revenue"], 50)
        self.assertEqual(result["summary"]["invoice_count"], 1)
        self.assertEqual([row["revenue"] for row in result["daily"]], [50, 0])
        self.assertEqual(result["growth"], 100)
        self.assertEqual(result["previous_start"], date(2026, 3, 6))
        self.assertEqual(result["previous_end"], date(2026, 3, 7))
        self.assertEqual(
            prev.call_args.args[1:], (datetime(2026, 3, 6, 8), datetime(2026, 3, 8, 8))
        )


class ImageSuggestionTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(AI_VISION_ENABLED=False)
        stream = BytesIO()
        Image.new("RGB", (20, 20), "white").save(stream, format="PNG")
        self.image = stream.getvalue()

    @contextmanager
    def connection(self):
        yield object()

    def test_local_without_api_key_only_suggests_color_never_species_or_eyes(self):
        with self.app.app_context(), patch.object(
            pet_image_service, "read_connection", self.connection
        ), patch.object(pet_image_service, "require_actor"), patch.object(
            pet_image_service.ai_client, "complete"
        ) as api:
            result = pet_image_service.suggest_attributes(1, self.image)
        api.assert_not_called()
        self.assertEqual(result["mode"], "local")
        self.assertEqual(set(result["suggestions"]), {"coat_color"})
        self.assertIn("trắng", result["suggestions"]["coat_color"])

    def test_network_failure_keeps_local_suggestions(self):
        self.app.config["AI_VISION_ENABLED"] = True
        with self.app.app_context(), patch.object(
            pet_image_service, "read_connection", self.connection
        ), patch.object(pet_image_service, "require_actor"), patch.object(
            pet_image_service.ai_client, "is_configured", return_value=True
        ), patch.object(
            pet_image_service.ai_client,
            "complete",
            side_effect=AIProviderError("offline"),
        ):
            result = pet_image_service.suggest_attributes(1, self.image)
        self.assertEqual(result["mode"], "local")
        self.assertTrue(result["warning"])
        self.assertIn("coat_color", result["suggestions"])

    def test_vision_values_are_bounded_and_do_not_generate_a_breed(self):
        with self.app.app_context(), patch.object(
            pet_image_service, "read_connection", self.connection
        ), patch.object(pet_image_service, "require_actor"), patch.object(
            pet_image_service,
            "_analysis_from_model",
            return_value=(
                {
                    "species": "Mèo",
                    "coat_color": "x" * 100,
                    "eye_color": "x" * 100,
                    "coat_pattern": "vằn",
                    "shape": "nhỏ",
                },
                None,
                "used",
            ),
        ):
            result = pet_image_service.suggest_attributes(1, self.image)
        self.assertEqual(len(result["suggestions"]["coat_color"]), 80)
        self.assertEqual(len(result["suggestions"]["eye_color"]), 60)
        self.assertNotIn("breed", result["suggestions"])
        self.assertEqual(result["mode"], "vision")

    def test_vision_breed_and_fine_grained_traits_are_offered_for_review(self):
        with self.app.app_context(), patch.object(
            pet_image_service, "read_connection", self.connection
        ), patch.object(pet_image_service, "require_actor"), patch.object(
            pet_image_service,
            "_analysis_from_model",
            return_value=(
                {
                    "species": "Mèo",
                    "breed": "Mèo Anh lông ngắn",
                    "coat_color": "xám",
                    "coat_pattern": "mướp",
                    "coat_length": "ngắn",
                    "size": "nhỏ",
                    "eye_color": "vàng",
                    "shape": "mặt tròn",
                },
                None,
                "used",
            ),
        ):
            result = pet_image_service.suggest_attributes(1, self.image)

        self.assertEqual(result["suggestions"]["breed"], "Mèo Anh lông ngắn")
        self.assertIn("mướp", result["suggestions"]["appearance_tags"])
        self.assertIn("ngắn", result["suggestions"]["appearance_tags"])
        self.assertIn("nhỏ", result["suggestions"]["appearance_tags"])

    def test_identical_image_explains_color_and_structure(self):
        descriptor = describe_image(self.image)
        self.assertEqual(
            similarity_components(descriptor, descriptor), {"color": 1, "structure": 1}
        )

    def test_image_filters_are_validated_before_processing(self):
        with self.assertRaises(ValidationError):
            pet_image_service.search_similar(1, self.image, status="sold OR 1=1")

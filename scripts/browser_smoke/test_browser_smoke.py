"""Isolated Chromium smoke coverage for core Petcare Manager browser flows."""

from __future__ import annotations

import json
import http.client
import os
import re
# The suite must supervise a local Flask process so it can always stop the server.
import subprocess  # nosec B404
import sys
import tempfile
import time
import unittest
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

from petcare.config import Config
from petcare.database.connection import get_connection, transaction
from petcare.database.initialize import initialize_database
from petcare.database.seed import USERS, seed_database
from petcare.money import format_money, format_number
from petcare.repositories.base import fetch_one
from petcare.services import (
    customer_service, invoice_service, pet_service, product_service,
    purchase_service, report_service,
)
from petcare.services.tenant_export_storage import get_export_storage

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = Path(
    os.environ.get(
        "PLAYWRIGHT_ARTIFACT_DIR",
            str(Path(tempfile.gettempdir()) / "petcare-phase35-browser-artifacts"),
    )
).resolve()
BASE_URL = f"http://127.0.0.1:{Config.APP_PORT}"
SEED_PASSWORDS = {username: password for username, password, _name, _role in USERS}


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")


def _path_only(url: str) -> str:
    return urlsplit(url).path


class BrowserSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_db = os.getenv("PETCARE_TEST_DB_NAME", "")
        if not re.fullmatch(r"[A-Za-z0-9_]+_test", test_db):
            raise RuntimeError(
                "Browser smoke requires PETCARE_TEST_DB_NAME to name an isolated schema ending _test."
            )
        if Config.DB_NAME != test_db:
            raise RuntimeError("DB_NAME and PETCARE_TEST_DB_NAME must be the same isolated schema.")
        if Config.APP_PORT < 1024:
            raise RuntimeError("Browser smoke requires an unprivileged localhost port.")

        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        ARTIFACT_DIR.chmod(0o700)
        initialize_database()
        seed_database()
        with get_connection() as connection:
            cls.tenant_id = fetch_one(
                connection, "SELECT id FROM tenants WHERE slug = 'main'"
            )["id"]
            cls.admin_id = fetch_one(
                connection, "SELECT id FROM users WHERE username = 'admin'"
            )["id"]

        cls._runtime_log = (ARTIFACT_DIR / "runtime.log").open("ab")
        child_env = os.environ.copy()
        child_env.update(
            {
                "APP_ENV": "test",
                "APP_PORT": str(Config.APP_PORT),
                "PUBLIC_BASE_URL": BASE_URL,
                "COOKIE_SECURE": "0",
                "LAN_ACCESS_ENABLED": "0",
                "AI_API_BASE_URL": "",
                "AI_API_KEY": "",
                "AI_MODEL": "",
                "MAIL_HOST": "",
                "MEDIA_STORAGE_BACKEND": "local",
                "TENANT_EXPORT_STORAGE_BACKEND": "local",
            }
        )
        # Launch only the repository's fixed entry point; no shell or request input reaches argv.
        cls._server = subprocess.Popen(  # nosec B603
            [sys.executable, str(ROOT / "run.py")],
            cwd=ROOT,
            env=child_env,
            stdout=cls._runtime_log,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 35
        last_error = None
        ready = False
        while time.monotonic() < deadline:
            if cls._server.poll() is not None:
                raise RuntimeError(f"Flask process exited with {cls._server.returncode}.")
            try:
                probe = http.client.HTTPConnection("127.0.0.1", Config.APP_PORT, timeout=1)
                try:
                    probe.request("GET", "/readyz")
                    response = probe.getresponse()
                    if response.status == 200:
                        ready = True
                        break
                    last_error = f"/readyz returned {response.status}"
                finally:
                    probe.close()
            except (TimeoutError, OSError) as exc:
                last_error = type(exc).__name__
            time.sleep(0.2)
        if not ready:
            cls._server.terminate()
            cls._server.wait(timeout=10)
            raise RuntimeError(f"Flask QA server did not become ready: {last_error}")
        for path in ("/healthz", "/readyz"):
            probe = http.client.HTTPConnection("127.0.0.1", Config.APP_PORT, timeout=2)
            try:
                probe.request("GET", path)
                response = probe.getresponse()
                response.read()
                if response.status != 200:
                    raise RuntimeError(f"{path} returned {response.status} on the isolated QA schema.")
            finally:
                probe.close()

        cls._playwright = sync_playwright().start()
        cls._browser = cls._playwright.chromium.launch(headless=True)
        cls._network_summary = []
        cls._axe_results = []

    @classmethod
    def tearDownClass(cls):
        browser = getattr(cls, "_browser", None)
        if browser:
            browser.close()
        playwright = getattr(cls, "_playwright", None)
        if playwright:
            playwright.stop()
        server = getattr(cls, "_server", None)
        if server and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        runtime_log = getattr(cls, "_runtime_log", None)
        if runtime_log:
            runtime_log.close()
        summary_path = ARTIFACT_DIR / "browser-diagnostics.json"
        summary_path.write_text(
            json.dumps(cls._network_summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summary_path.chmod(0o600)
        if getattr(cls, "_axe_results", None):
            axe_path = ARTIFACT_DIR / "axe-results.json"
            axe_path.write_text(
                json.dumps(cls._axe_results, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            axe_path.chmod(0o600)

    def setUp(self):
        self.context = self._browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )
        self.context.tracing.start(screenshots=True, snapshots=False, sources=False)
        self.page = self.context.new_page()
        self._axe_route_installed = False
        self.page.set_default_timeout(10_000)
        self.console_errors = []
        self.page_errors = []
        self.failed_requests = []
        self.http_errors = []
        self.refund_posts = []
        self.page.on(
            "console",
            lambda message: self.console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.on(
            "requestfailed",
            lambda request: self.failed_requests.append(
                {"method": request.method, "path": _path_only(request.url), "failure": request.failure}
            ),
        )
        self.page.on(
            "response",
            lambda response: self.http_errors.append(
                {
                    "method": response.request.method,
                    "path": _path_only(response.url),
                    "status": response.status,
                }
            )
            if response.status >= 400
            else None,
        )
        self.page.on(
            "request",
            lambda request: self.refund_posts.append(_path_only(request.url))
            if request.method == "POST" and _path_only(request.url).endswith("/refund")
            else None,
        )

    def tearDown(self):
        stem = _safe_name(self.id().split(".")[-1])
        try:
            if self.page and not self.page.is_closed():
                self.page.evaluate("document.activeElement?.blur(); window.scrollTo({top: 0, left: 0, behavior: 'instant'})")
                screenshot = ARTIFACT_DIR / f"{stem}-final.png"
                self.page.screenshot(path=str(screenshot), full_page=True, animations="disabled")
                screenshot.chmod(0o600)
        finally:
            trace = ARTIFACT_DIR / f"{stem}-trace.zip"
            self.context.tracing.stop(path=str(trace))
            trace.chmod(0o600)
            self.context.close()
            self.__class__._network_summary.append(
                {
                    "test": self.id(),
                    "console_errors": self.console_errors,
                    "page_errors": self.page_errors,
                    "failed_requests": self.failed_requests,
                    "http_errors": self.http_errors,
                    "refund_posts": len(self.refund_posts),
                }
            )

    def _login(self, username="admin"):
        self.page.goto(BASE_URL + "/login", wait_until="domcontentloaded")
        self.page.locator('input[name="store_slug"]').fill("main")
        self.page.locator('input[name="username"]').fill(username)
        self.page.locator('input[name="password"]').fill(SEED_PASSWORDS[username])
        self.page.locator('.login-card form button[type="submit"]').click()
        self.page.wait_for_url(BASE_URL + "/dashboard", timeout=10_000)

    def _assert_browser_diagnostics(self, *, expected_forbidden_users=False):
        allowed_http = {("GET", "/favicon.ico", 404)}
        if expected_forbidden_users:
            allowed_http.add(("GET", "/users/", 403))
        unexpected = [
            item
            for item in self.http_errors
            if (item["method"], item["path"], item["status"]) not in allowed_http
        ]
        self.assertEqual(unexpected, [], f"Unexpected HTTP error responses: {unexpected}")
        self.assertEqual(self.failed_requests, [], f"Failed browser requests: {self.failed_requests}")
        self.assertEqual(self.page_errors, [], f"JavaScript exceptions: {self.page_errors}")
        expected_denial_console = []
        if expected_forbidden_users and any(
            item["method"] == "GET" and item["path"] == "/users/" and item["status"] == 403
            for item in self.http_errors
        ):
            expected_denial_console = [
                message for message in self.console_errors if "403 (FORBIDDEN)" in message
            ]
        remaining_console = list(self.console_errors)
        for message in expected_denial_console[:1]:
            remaining_console.remove(message)
        self.assertEqual(remaining_console, [], f"Console errors: {remaining_console}")

    def _accessibility_smoke(self):
        audit = self.page.evaluate(
            """() => {
              const visible = node => !!(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
              const hasName = node => Boolean(
                node.getAttribute('aria-label') || node.getAttribute('aria-labelledby') ||
                node.getAttribute('title') || (node.innerText || node.textContent || '').trim() ||
                [...(node.querySelectorAll?.('img[alt]') || [])].some(img => img.alt.trim())
              );
              const unnamedButtons = [...document.querySelectorAll('button')]
                .filter(node => visible(node) && !node.disabled && !hasName(node));
              const unlabeledControls = [...document.querySelectorAll('input:not([type=hidden]):not([type=submit]):not([type=button]), select, textarea')]
                .filter(node => visible(node) && !node.disabled && !node.labels?.length &&
                  !node.getAttribute('aria-label') && !node.getAttribute('aria-labelledby'));
              return {
                main_landmark: !!document.querySelector('main,[role="main"]'),
                unnamed_buttons: unnamedButtons.map(node => node.outerHTML.slice(0, 180)),
                unlabeled_controls: unlabeledControls.map(node => node.outerHTML.slice(0, 180))
              };
            }"""
        )
        self.assertTrue(audit["main_landmark"], "Page must expose a main landmark.")
        self.assertEqual(audit["unnamed_buttons"], [], f"Unnamed buttons: {audit['unnamed_buttons']}")
        self.assertEqual(
            audit["unlabeled_controls"], [], f"Unlabeled controls: {audit['unlabeled_controls']}"
        )

    def _save_page_screenshot(self, name):
        path = ARTIFACT_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.page.evaluate("document.activeElement?.blur(); window.scrollTo({top: 0, left: 0, behavior: 'instant'})")
        self.page.screenshot(path=str(path), full_page=True, animations="disabled")
        path.chmod(0o600)
        return path

    def _save_phase43_screenshot(self, name):
        root = ARTIFACT_DIR / "phase43" if os.getenv("PETCARE_PRESERVE_DOC_ASSETS") == "1" else ROOT / "docs" / "assets" / "phase43"
        path = root / "after" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        self.page.evaluate("document.activeElement?.blur(); window.scrollTo({top: 0, left: 0, behavior: 'instant'})")
        self.page.screenshot(path=str(path), full_page=True, animations="disabled")
        path.chmod(0o644)
        return path

    def _save_phase54_screenshot(self, name):
        root = ARTIFACT_DIR / "phase54" if os.getenv("PETCARE_PRESERVE_DOC_ASSETS") == "1" else ROOT / "docs" / "assets" / "phase54"
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        self.page.evaluate("document.activeElement?.blur(); window.scrollTo({top: 0, left: 0, behavior: 'instant'})")
        self.page.screenshot(path=str(path), full_page=False, animations="disabled")
        path.chmod(0o644)
        return path

    def _save_phase55_screenshot(self, name):
        root = (
            ARTIFACT_DIR / "phase55"
            if os.getenv("PETCARE_PRESERVE_DOC_ASSETS") == "1"
            else ROOT / "docs" / "assets" / "phase55"
        )
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        self.page.evaluate("document.activeElement?.blur(); window.scrollTo({top: 0, left: 0, behavior: 'instant'})")
        self.page.screenshot(path=str(path), full_page=False, animations="disabled")
        path.chmod(0o644)
        return path

    def _axe_audit(self, screen):
        axe_path = os.getenv("AXE_CORE_PATH", "")
        if not axe_path:
            return
        # The longest shared or POS-card entrance is under 0.65s. Wait past it
        # so contrast is measured on the stable UI, not a temporary fade frame.
        self.page.wait_for_timeout(700)
        if self.page.evaluate("typeof window.axe === 'undefined'"):
            if not self._axe_route_installed:
                axe_source = Path(axe_path).read_bytes()
                self.page.route(
                    f"{BASE_URL}/__phase42_axe__.js",
                    lambda route: route.fulfill(
                        status=200,
                        content_type="application/javascript; charset=utf-8",
                        body=axe_source,
                    ),
                )
                self._axe_route_installed = True
            self.page.add_script_tag(url=f"{BASE_URL}/__phase42_axe__.js")
        result = self.page.evaluate("""async () => {
          const report = await window.axe.run(document);
          const simplify = rule => ({
            id: rule.id, impact: rule.impact, help: rule.help, help_url: rule.helpUrl,
            nodes: rule.nodes.map(node => ({target: node.target, summary: node.failureSummary}))
          });
          return {
            version: window.axe.version,
            violations: report.violations.map(simplify),
            incomplete: report.incomplete.map(simplify)
          };
        }""")
        self.__class__._axe_results.append({"screen": screen, **result})
        blockers = [
            {"id": item["id"], "impact": item["impact"], "nodes": item["nodes"]}
            for item in result["violations"]
            if item["impact"] in {"critical", "serious"}
        ]
        self.assertEqual(blockers, [], f"Serious axe violations in {screen}: {blockers}")

    def test_admin_navigation_modules_responsive_pos_and_accessibility(self):
        self._login("admin")
        routes = (
            ("/dashboard", None),
            ("/customers/", "Khách hàng"),
            ("/pets/", "Thú cưng"),
            ("/products/", "Sản phẩm"),
            ("/invoices/", "Hóa đơn"),
            ("/purchasing/", "Đơn nhập hàng"),
            ("/reports/", "Báo cáo"),
        )
        for path, heading in routes:
            with self.subTest(path=path):
                response = self.page.goto(BASE_URL + path, wait_until="domcontentloaded")
                self.assertEqual(response.status, 200, f"GET {path}")
                if heading:
                    expect(self.page.get_by_role("heading", name=heading, exact=True).first).to_be_visible()
                else:
                    expect(self.page.get_by_role("heading", level=1).first).to_be_visible()
                self._accessibility_smoke()

        product_id = None
        with get_connection() as connection:
            product_id = fetch_one(
                connection, "SELECT id FROM products WHERE code = 'FOOD-003'"
            )["id"]
        response = self.page.goto(BASE_URL + f"/products/{product_id}/edit", wait_until="domcontentloaded")
        self.assertEqual(response.status, 200)
        quantity = self.page.locator('input[name="quantity_delta"]')
        reason = self.page.locator('input[name="reason"]')
        quantity.focus()
        self.page.keyboard.press("Tab")
        self.assertEqual(self.page.evaluate("document.activeElement.name"), "reason")

        self.page.set_viewport_size({"width": 820, "height": 1180})
        self.page.goto(BASE_URL + "/dashboard", wait_until="domcontentloaded")
        self.page.locator('.side-nav > .nav-link[href="/reports/"]').click()
        self.page.wait_for_url("**/reports/")
        expect(self.page.get_by_role("heading", name="Báo cáo", exact=True)).to_be_visible()

        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.goto(BASE_URL + "/invoices/new", wait_until="domcontentloaded")
        self._accessibility_smoke()
        initial = self.page.locator("[data-pos-mobile-total]").inner_text()
        self.page.locator("button[data-pos-item]:not([disabled])").first.click()
        count = self.page.locator("[data-pos-mobile-count]")
        expect(count).to_contain_text("1")
        expect(self.page.locator("[data-pos-mobile-total]")).to_have_text(
            self.page.locator("#estimate").inner_text()
        )
        self.assertNotEqual(self.page.locator("[data-pos-mobile-total]").inner_text(), initial)
        self.page.locator(".pos-mobile-cart").click()
        self.assertTrue(self.page.url.endswith("#pos-order"))
        self.page.locator("#pos-order").scroll_into_view_if_needed()
        screenshot = ARTIFACT_DIR / "mobile-pos-cart.png"
        self.page.evaluate("document.activeElement?.blur(); window.scrollTo({top: 0, left: 0, behavior: 'instant'})")
        self.page.screenshot(path=str(screenshot), full_page=True, animations="disabled")
        screenshot.chmod(0o600)
        self._assert_browser_diagnostics()

    def test_staff_role_restriction_and_allowed_customer_access(self):
        self._login("staff1")
        response = self.page.goto(BASE_URL + "/customers/", wait_until="domcontentloaded")
        self.assertEqual(response.status, 200)
        expect(self.page.get_by_role("heading", name="Khách hàng", exact=True)).to_be_visible()
        response = self.page.goto(BASE_URL + "/users/", wait_until="domcontentloaded")
        self.assertEqual(response.status, 403)
        expect(self.page.get_by_role("heading").first).to_be_visible()
        self._assert_browser_diagnostics(expected_forbidden_users=True)

    def test_purchase_order_create_partial_full_receive_and_close(self):
        """Exercise the real PO form and receipt routes with synthetic MySQL rows."""
        fixture = {"supplier_id": None, "product_id": None, "order_ids": []}
        self.addCleanup(self._cleanup_purchase_fixture, fixture)
        self._login("admin")
        suffix = uuid4().hex[:8].upper()
        fixture["supplier_id"] = purchase_service.create_supplier(
            self.admin_id,
            {"name": f"Phase43 supplier {suffix}", "contact_name": "", "phone": "",
             "email": "", "address": ""},
            tenant_id=self.tenant_id,
        )
        fixture["product_id"] = product_service.create_product(
            self.admin_id,
            {"code": f"P43-{suffix}", "name": f"Phase43 product {suffix}",
             "category": "QA", "description": "Synthetic purchasing browser fixture",
             "unit_price": "10000", "stock_qty": "2", "reorder_level": "0"},
            tenant_id=self.tenant_id,
        )
        product_id = fixture["product_id"]
        with get_connection() as connection:
            initial_stock = fetch_one(
                connection, "SELECT stock_qty FROM products WHERE tenant_id=%s AND id=%s",
                (self.tenant_id, product_id),
            )["stock_qty"]
        for width in (320, 390, 768, 820, 1024, 1440):
            self.page.set_viewport_size({"width": width, "height": 900 if width < 600 else 1024})
            self.page.goto(BASE_URL + f"/products/{product_id}/edit", wait_until="domcontentloaded")
            self.assertEqual(
                self.page.evaluate("document.documentElement.scrollWidth"), width,
                f"Stock adjustment page overflows at {width}px.",
            )
            self._accessibility_smoke()
            if width == 320:
                self.page.locator('input[name="quantity_delta"]').focus()
                self.page.keyboard.press("Tab")
                self.assertEqual(self.page.evaluate("document.activeElement.name"), "reason")
            if width in (320, 1440):
                if os.getenv("AXE_CORE_PATH"):
                    self._axe_audit(f"phase43-stock-adjustment-{width}")
                self._save_phase43_screenshot(f"stock-adjustment-{width}.png")

        self.page.set_viewport_size({"width": 1440, "height": 960})
        self.page.goto(BASE_URL + "/purchasing/new", wait_until="domcontentloaded")
        self.page.locator('select[name="supplier_id"]').select_option(str(fixture["supplier_id"]))
        self.page.locator("[data-product-query]").fill(f"P43-{suffix}")
        add_product = self.page.locator(f'[data-add-product][data-product-code="P43-{suffix}"]')
        expect(add_product).to_be_visible()
        add_product.click()
        expect(self.page.locator("[data-order-line]")).to_have_count(1)
        self.page.locator('[data-order-line] input[name="quantity[]"]').fill("5")
        self.page.locator('[data-order-line] input[name="unit_cost[]"]').fill("4000")
        self.assertIn("20.000", self.page.locator("[data-order-estimate]").inner_text())
        self._save_phase43_screenshot("purchasing-create-1440.png")
        self.page.get_by_role("button", name="Tạo đơn nhập").click()
        self.page.wait_for_url(re.compile(r"/purchasing/\d+$"))
        order_id = int(self.page.url.rstrip("/").split("/")[-1])
        fixture["order_ids"].append(order_id)
        with get_connection() as connection:
            order_row = fetch_one(
                connection, "SELECT status,total_amount FROM purchase_orders WHERE tenant_id=%s AND id=%s",
                (self.tenant_id, order_id),
            )
            item = fetch_one(
                connection, "SELECT id,quantity_ordered,quantity_received FROM purchase_order_items "
                "WHERE tenant_id=%s AND purchase_order_id=%s",
                (self.tenant_id, order_id),
            )
        self.assertEqual((order_row["status"], order_row["total_amount"]), ("ordered", 20000))
        self.assertEqual((item["quantity_ordered"], item["quantity_received"]), (5, 0))
        self.assertEqual(initial_stock, 2, "Creating a purchase order must not change on-hand stock.")

        widths = (320, 390, 768, 820, 1024, 1440)
        for width in widths:
            self.page.set_viewport_size({"width": width, "height": 900 if width < 600 else 1024})
            self.page.goto(BASE_URL + "/purchasing/?status=ordered", wait_until="domcontentloaded")
            self.assertEqual(
                self.page.evaluate("document.documentElement.scrollWidth"), width,
                f"Purchase list overflows at {width}px.",
            )
            list_selector = ".purchase-mobile-orders" if width <= 680 else ".purchase-table"
            order_link = self.page.locator(f'{list_selector} a[href="/purchasing/{order_id}"]').first
            expect(order_link).to_be_visible()
            if width <= 680:
                expect(self.page.locator(".purchase-mobile-orders")).to_be_visible()
                expect(self.page.locator(".purchase-list-panel > .table-scroll:not(.purchase-detail-table-scroll)")).to_be_hidden()
            else:
                expect(self.page.locator(".purchase-mobile-orders")).to_be_hidden()
                expect(self.page.get_by_role(
                    "region", name=re.compile("Danh sách đơn nhập")
                )).to_be_visible()
            self._accessibility_smoke()
            if width in (320, 1440):
                if os.getenv("AXE_CORE_PATH"):
                    self._axe_audit(f"phase43-purchasing-list-{width}")
                self._save_phase43_screenshot(f"purchasing-list-{width}.png")

        for width in widths:
            self.page.set_viewport_size({"width": width, "height": 900 if width < 600 else 1024})
            self.page.goto(BASE_URL + f"/purchasing/{order_id}", wait_until="domcontentloaded")
            self.assertEqual(
                self.page.evaluate("document.documentElement.scrollWidth"), width,
                f"Purchase detail overflows at {width}px.",
            )
            if width <= 680:
                expect(self.page.locator(".purchase-mobile-lines")).to_be_visible()
                expect(self.page.locator(".purchase-detail-table-scroll")).to_be_hidden()
                expect(self.page.locator(".purchase-mobile-line").first).to_contain_text("Còn thiếu")
            else:
                expect(self.page.locator(".purchase-detail-table-scroll")).to_be_visible()
                expect(self.page.locator(".purchase-mobile-lines")).to_be_hidden()
            self._accessibility_smoke()
            if width in (320, 1440):
                if os.getenv("AXE_CORE_PATH"):
                    self._axe_audit(f"phase43-purchasing-detail-ordered-{width}")
                self._save_phase43_screenshot(f"purchasing-detail-ordered-{width}.png")

        self.page.set_viewport_size({"width": 320, "height": 900})
        self.page.goto(BASE_URL + f"/purchasing/{order_id}", wait_until="domcontentloaded")
        receive = self.page.locator("[data-purchase-receive-form]")
        quantity = receive.locator('input[name="quantity[]"]')
        quantity.fill("2")
        receive.get_by_role("button", name="Xác nhận nhận hàng").click()
        expect(self.page.locator(".flash-success")).to_contain_text("có thể nhận tiếp")
        with get_connection() as connection:
            order_state = fetch_one(
                connection, "SELECT status FROM purchase_orders WHERE tenant_id=%s AND id=%s",
                (self.tenant_id, order_id),
            )["status"]
            item_state = fetch_one(
                connection, "SELECT quantity_received FROM purchase_order_items WHERE tenant_id=%s AND id=%s",
                (self.tenant_id, item["id"]),
            )["quantity_received"]
            stock_after_partial = fetch_one(
                connection, "SELECT stock_qty FROM products WHERE tenant_id=%s AND id=%s",
                (self.tenant_id, product_id),
            )["stock_qty"]
        self.assertEqual((order_state, item_state, stock_after_partial), ("partially_received", 2, 4))
        self._save_phase43_screenshot("purchasing-detail-partial-320.png")
        self.page.locator("[data-fill-remaining]").focus()
        self.page.keyboard.press("Enter")
        expect(receive.locator('input[name="quantity[]"]')).to_have_value("3")
        expect(receive.locator("[data-receive-feedback]")).to_contain_text("3 đơn vị")
        self.page.get_by_role("button", name="Xác nhận nhận hàng").click()
        expect(self.page.locator(".flash-success")).to_contain_text("đã hoàn tất")
        with get_connection() as connection:
            order_state = fetch_one(
                connection, "SELECT status FROM purchase_orders WHERE tenant_id=%s AND id=%s",
                (self.tenant_id, order_id),
            )["status"]
            item_state = fetch_one(
                connection, "SELECT quantity_received FROM purchase_order_items WHERE tenant_id=%s AND id=%s",
                (self.tenant_id, item["id"]),
            )["quantity_received"]
            movements = fetch_one(
                connection, "SELECT COUNT(*) total FROM stock_movements WHERE tenant_id=%s "
                "AND purchase_order_id=%s", (self.tenant_id, order_id),
            )["total"]
            final_stock = fetch_one(
                connection, "SELECT stock_qty FROM products WHERE tenant_id=%s AND id=%s",
                (self.tenant_id, product_id),
            )["stock_qty"]
        self.assertEqual((order_state, item_state, final_stock, movements), ("received", 5, 7, 2))
        for width in (320, 1440):
            self.page.set_viewport_size({"width": width, "height": 900})
            self.page.goto(BASE_URL + f"/purchasing/{order_id}", wait_until="domcontentloaded")
            self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
            if os.getenv("AXE_CORE_PATH"):
                self._axe_audit(f"phase43-purchasing-detail-received-{width}")
            self._save_phase43_screenshot(f"purchasing-detail-received-{width}.png")

        cancelled_id = purchase_service.create_purchase_order(
            self.admin_id,
            {"supplier_id": str(fixture["supplier_id"]), "note": "QA cancel route"},
            [{"product_id": str(product_id), "quantity": "2", "unit_cost": "4000"}],
            tenant_id=self.tenant_id,
        )
        fixture["order_ids"].append(cancelled_id)
        self.page.goto(BASE_URL + f"/purchasing/{cancelled_id}", wait_until="domcontentloaded")
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.get_by_role("button", name="Đóng phần còn lại").click()
        expect(self.page.locator(".flash-success")).to_contain_text("được giữ trong lịch sử")
        with get_connection() as connection:
            cancelled_state = fetch_one(
                connection, "SELECT status FROM purchase_orders WHERE tenant_id=%s AND id=%s",
                (self.tenant_id, cancelled_id),
            )["status"]
            after_cancel_stock = fetch_one(
                connection, "SELECT stock_qty FROM products WHERE tenant_id=%s AND id=%s",
                (self.tenant_id, product_id),
            )["stock_qty"]
        self.assertEqual((cancelled_state, after_cancel_stock), ("cancelled", 7))
        self._assert_browser_diagnostics()

    def test_reports_real_filters_values_export_and_responsive_products(self):
        self._login("admin")
        expected = report_service.report(self.admin_id, period="7d", tenant_id=self.tenant_id)
        widths = (320, 390, 768, 820, 1024, 1440)
        for width in widths:
            self.page.set_viewport_size({"width": width, "height": 900 if width < 600 else 1024})
            response = self.page.goto(BASE_URL + "/reports/?period=7d", wait_until="domcontentloaded")
            self.assertEqual(response.status, 200)
            self.assertEqual(
                self.page.evaluate("document.documentElement.scrollWidth"), width,
                f"Reports overflows at {width}px.",
            )
            expect(self.page.get_by_role("heading", name="Báo cáo", exact=True)).to_be_visible()
            expect(self.page.locator('.quick-periods a[aria-current="page"]')).to_have_text("7 ngày")
            self.assertEqual(
                self.page.locator(".report-stats .stat-card").nth(0).locator("strong").inner_text(),
                format_money(expected["summary"]["revenue"], expected["currency_code"], "vi_VN"),
            )
            self.assertEqual(
                self.page.locator(".report-stats .stat-card").nth(1).locator("strong").inner_text(),
                format_number(expected["summary"]["invoice_count"], "vi_VN"),
            )
            if width <= 680:
                expect(self.page.locator(".report-mobile-products")).to_be_visible()
                expect(self.page.locator(".report-products-table")).to_be_hidden()
                if expected["top_products"]:
                    expect(self.page.locator(".report-mobile-product").first).to_contain_text(
                        expected["top_products"][0]["name"]
                    )
                    expect(self.page.locator(".report-mobile-product").first).to_contain_text(
                        str(expected["top_products"][0]["quantity_sold"])
                    )
            else:
                expect(self.page.locator(".report-products-table")).to_be_visible()
                expect(self.page.locator(".report-mobile-products")).to_be_hidden()
            self._accessibility_smoke()
            if width in (320, 1440):
                if os.getenv("AXE_CORE_PATH"):
                    self._axe_audit(f"phase43-reports-{width}")
                self._save_phase43_screenshot(f"reports-{width}.png")

        self.page.set_viewport_size({"width": 1440, "height": 960})
        self.page.goto(BASE_URL + "/reports/?period=7d", wait_until="domcontentloaded")
        self.page.locator("#report-start").fill(expected["start_date"].isoformat())
        self.page.locator("#report-end").fill(expected["end_date"].isoformat())
        self.page.get_by_role("button", name="Xem báo cáo theo kỳ").click()
        self.page.wait_for_url(re.compile(r"/reports/\?start=.*&end=.*"))
        expect(self.page.locator("#report-start")).to_have_value(expected["start_date"].isoformat())
        expect(self.page.locator("#report-end")).to_have_value(expected["end_date"].isoformat())
        with self.page.expect_download() as downloaded:
            self.page.locator('[data-report-export] button[type="submit"]').click()
        download = downloaded.value
        self.assertTrue(download.suggested_filename.endswith(".xlsx"))
        self.assertTrue(download.path())
        with open(download.path(), "rb") as exported:
            self.assertTrue(exported.read(4).startswith(b"PK"))
        self._assert_browser_diagnostics()

    def test_assistant_top_products_renders_live_report_facts_on_mobile(self):
        self._login("admin")
        expected = report_service.top_products_for_period(
            self.admin_id, "week", tenant_id=self.tenant_id
        )
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), 390)
        self.page.get_by_role("button", name="Hỏi trợ lý").click()
        self.page.get_by_role("button", name="Bán chạy tuần này").click()
        insight = self.page.locator(".assistant-insight")
        expect(insight).to_be_visible()
        expect(insight.locator("strong").first).to_contain_text("Báo cáo bán hàng · tuần này")
        if expected["items"]:
            first = expected["items"][0]
            card = self.page.locator(".assistant-insight .assistant-result-card").first
            expect(card).to_contain_text(first["name"])
            expect(card).to_contain_text(str(first["quantity_sold"]))
            expect(card.locator("a")).to_have_attribute("href", f"/products/{first['product_id']}")
        else:
            expect(insight).to_contain_text("Không có sản phẩm bán trong kỳ này.")
        expect(self.page.locator(".assistant-message-source").last).to_contain_text(
            "Báo cáo bán hàng · dữ liệu MySQL"
        )
        self._accessibility_smoke()
        self._assert_browser_diagnostics()

    def test_assistant_inventory_and_purchase_insights_are_responsive_and_navigable(self):
        fixture = {"supplier_id": None, "product_ids": [], "order_ids": []}
        self.addCleanup(self._cleanup_purchase_fixture, fixture)
        suffix = uuid4().hex[:8].upper()
        self._login("admin")
        toast_close = self.page.locator(".toast-close")
        if toast_close.count():
            toast_close.first.click()
        fixture["supplier_id"] = purchase_service.create_supplier(
            self.admin_id,
            {"name": f"Phase54 synthetic supplier {suffix}", "contact_name": "", "phone": "",
             "email": "", "address": ""},
            tenant_id=self.tenant_id,
        )
        inventory_product_id = product_service.create_product(
            self.admin_id,
            {"code": f"P54-I-{suffix}", "name": f"000 Phase54 inventory {suffix}",
             "category": "Synthetic QA", "description": "Browser-only assistant fixture",
             "unit_price": "1000", "stock_qty": "0", "reorder_level": "0"},
            tenant_id=self.tenant_id,
        )
        fixture["product_ids"].append(inventory_product_id)
        order_product_id = product_service.create_product(
            self.admin_id,
            {"code": f"P54-P-{suffix}", "name": f"Phase54 purchasing {suffix}",
             "category": "Synthetic QA", "description": "Browser-only assistant fixture",
             "unit_price": "1000", "stock_qty": "10", "reorder_level": "0"},
            tenant_id=self.tenant_id,
        )
        fixture["product_ids"].append(order_product_id)
        for status in ("ordered", "partially_received", "received", "cancelled"):
            order_id = purchase_service.create_purchase_order(
                self.admin_id,
                {"supplier_id": str(fixture["supplier_id"]), "note": "Phase54 synthetic QA"},
                [{"product_id": str(order_product_id), "quantity": "4", "unit_cost": "1250"}],
                tenant_id=self.tenant_id,
            )
            fixture["order_ids"].append(order_id)
            if status in {"partially_received", "received"}:
                with get_connection() as connection:
                    item_id = fetch_one(
                        connection,
                        "SELECT id FROM purchase_order_items WHERE tenant_id=%s AND purchase_order_id=%s",
                        (self.tenant_id, order_id),
                    )["id"]
                quantity = 1 if status == "partially_received" else 4
                purchase_service.receive_purchase_order(
                    self.admin_id, order_id,
                    [{"item_id": str(item_id), "quantity": str(quantity)}],
                    tenant_id=self.tenant_id,
                )
            elif status == "cancelled":
                purchase_service.cancel_purchase_order(
                    self.admin_id, order_id, tenant_id=self.tenant_id,
                )

        self.page.set_viewport_size({"width": 1440, "height": 900})
        self.page.get_by_role("button", name="Hỏi trợ lý").click()
        self.page.get_by_role("button", name="Gợi ý nhập hàng").click()
        inventory = self.page.locator(".assistant-insight").last
        expect(inventory).to_be_visible()
        expect(inventory).to_contain_text("Phase54 inventory")
        expect(inventory.locator(f'a[href="/products/{inventory_product_id}"]')).to_be_visible()
        expect(self.page.locator(".assistant-message-source").last).to_contain_text("Service tồn kho chỉ đọc")
        if os.getenv("AXE_CORE_PATH"):
            self._axe_audit("phase54-assistant-inventory-desktop")
        self._save_phase54_screenshot("assistant-inventory-desktop.png")

        input_box = self.page.locator("#assistant-input")
        input_box.fill("Tình trạng đơn nhập?")
        input_box.press("Enter")
        purchasing = self.page.locator(".assistant-insight").last
        expect(purchasing).to_be_visible()
        expect(purchasing).to_contain_text("đang đặt: 1")
        expect(purchasing).to_contain_text("nhận một phần: 1")
        expect(purchasing).to_contain_text("đã nhận: 1")
        expect(purchasing).to_contain_text("đã hủy: 1")
        for order_id in fixture["order_ids"]:
            expect(purchasing.locator(f'a[href="/purchasing/{order_id}"]')).to_be_visible()
        expect(self.page.locator(".assistant-message-source").last).to_contain_text("dành cho quản trị viên")
        if os.getenv("AXE_CORE_PATH"):
            self._axe_audit("phase54-assistant-purchasing-desktop")
        self._save_phase54_screenshot("assistant-purchasing-desktop.png")

        for width in (320, 390, 768, 1440):
            self.page.set_viewport_size({"width": width, "height": 844 if width < 600 else 900})
            self.assertEqual(
                self.page.evaluate("document.documentElement.scrollWidth"), width,
                f"Assistant page overflows at {width}px.",
            )
            panel = self.page.locator("#assistant-panel")
            bounds = panel.bounding_box()
            self.assertGreaterEqual(bounds["x"], 0)
            self.assertLessEqual(bounds["x"] + bounds["width"], width)
            self._accessibility_smoke()
            if width == 390:
                if os.getenv("AXE_CORE_PATH"):
                    self._axe_audit("phase54-assistant-purchasing-mobile-390")
                self._save_phase54_screenshot("assistant-purchasing-mobile-390.png")
        self.page.keyboard.press("Escape")
        expect(self.page.locator("#assistant-panel")).to_be_hidden()
        expect(self.page.get_by_role("button", name="Hỏi trợ lý")).to_be_focused()
        self._assert_browser_diagnostics()

    def test_assistant_operations_overview_uses_live_services_and_reduces_interactions(self):
        fixture = {"supplier_id": None, "product_ids": [], "order_ids": []}
        self.addCleanup(self._cleanup_purchase_fixture, fixture)
        suffix = uuid4().hex[:8].upper()
        self._login("admin")
        toast_close = self.page.locator(".toast-close")
        if toast_close.count():
            toast_close.first.click()
        fixture["supplier_id"] = purchase_service.create_supplier(
            self.admin_id,
            {"name": f"Phase55 synthetic supplier {suffix}", "contact_name": "", "phone": "",
             "email": "", "address": ""},
            tenant_id=self.tenant_id,
        )
        product_id = product_service.create_product(
            self.admin_id,
            {"code": f"P55-{suffix}", "name": f"000 Phase55 low stock {suffix}",
             "category": "Synthetic QA", "description": "Isolated browser overview fixture",
             "unit_price": "1000", "stock_qty": "0", "reorder_level": "0"},
            tenant_id=self.tenant_id,
        )
        fixture["product_ids"].append(product_id)
        order_id = purchase_service.create_purchase_order(
            self.admin_id,
            {"supplier_id": str(fixture["supplier_id"]), "note": "Phase55 synthetic overview fixture"},
            [{"product_id": str(product_id), "quantity": "4", "unit_cost": "1250"}],
            tenant_id=self.tenant_id,
        )
        fixture["order_ids"].append(order_id)

        assistant_posts = []
        self.page.on(
            "request",
            lambda request: assistant_posts.append(request.url)
            if request.method == "POST" and request.url.endswith("/assistant/chat") else None,
        )
        self.page.set_viewport_size({"width": 1440, "height": 900})
        self.page.get_by_role("button", name="Hỏi trợ lý").click()
        self.page.get_by_role("button", name="Gợi ý nhập hàng").click()
        expect(self.page.locator(".assistant-message-source")).to_have_count(1)

        input_box = self.page.locator("#assistant-input")
        input_box.fill("Tình trạng đơn nhập?")
        input_box.press("Enter")
        expect(self.page.locator(".assistant-message-source")).to_have_count(2)
        input_box.fill("Sản phẩm nào bán chạy tuần này?")
        input_box.press("Enter")
        expect(self.page.locator(".assistant-message-source")).to_have_count(3)
        baseline_posts = len(assistant_posts)
        self.assertEqual(baseline_posts, 3)
        baseline_interactions = 1 + 1 + 2 * 2  # open + first suggestion + two typed question/send pairs

        self.page.locator("#assistant-clear").click()
        self.page.locator("#assistant-close").click()
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.get_by_role("button", name="Hỏi trợ lý").click()
        overview_prompt = self.page.get_by_role("button", name="Tổng quan cần chú ý")
        expect(overview_prompt).to_be_visible()
        overview_prompt.click()
        overview = self.page.locator(".assistant-operations-overview")
        expect(overview).to_be_visible()
        inventory = overview.locator('section[aria-label="Ưu tiên bổ sung tồn"]')
        purchasing = overview.locator('section[aria-label="Đơn nhập cần xử lý"]')
        sales = overview.locator('section[aria-label="Ngữ cảnh bán hàng · 7 ngày gần nhất"]')
        expect(inventory).to_contain_text("000 Phase55 low stock")
        expect(inventory.locator(f'a[href="/products/{product_id}"]')).to_be_visible()
        expect(purchasing).to_contain_text("đang đặt 1")
        expect(purchasing.locator(f'a[href="/purchasing/{order_id}"]')).to_be_visible()
        expect(purchasing.locator('a[href="/purchasing/"]')).to_be_visible()
        expect(sales).to_contain_text("202")
        expect(sales.locator('a[href^="/reports/?start="]')).to_be_visible()
        expect(self.page.locator(".assistant-message-source").last).to_contain_text("Tổng quan chỉ đọc")
        overview_posts = len(assistant_posts) - baseline_posts
        self.assertEqual(overview_posts, 1)
        overview_interactions = 2  # open assistant + choose the suggested overview
        self.assertLess(overview_interactions, baseline_interactions)
        if os.getenv("AXE_CORE_PATH"):
            self._axe_audit("phase55-operations-overview-mobile-top")

        for width in (320, 390, 768, 1440):
            self.page.set_viewport_size({"width": width, "height": 844 if width < 600 else 900})
            self.assertEqual(
                self.page.evaluate("document.documentElement.scrollWidth"), width,
                f"Operations overview overflows at {width}px.",
            )
            bounds = self.page.locator("#assistant-panel").bounding_box()
            self.assertGreaterEqual(bounds["x"], 0)
            self.assertLessEqual(bounds["x"] + bounds["width"], width)
            self.assertGreaterEqual(bounds["y"], 0)
            self.assertLessEqual(
                bounds["y"] + bounds["height"],
                844 if width < 600 else 900,
                f"Assistant panel is vertically clipped at {width}px.",
            )
            self._accessibility_smoke()
            if width == 390 and os.getenv("AXE_CORE_PATH"):
                self._axe_audit("phase55-operations-overview-mobile-390")

        self.page.set_viewport_size({"width": 390, "height": 844})
        expect(self.page.locator(".assistant-header")).to_be_visible()
        self.page.evaluate(
            "() => { const messages = document.getElementById('assistant-messages'); "
            "const overview = messages.querySelector('.assistant-operations-overview'); "
            "messages.scrollTop = overview.offsetTop; }"
        )
        self._save_phase55_screenshot("operations-overview-mobile-top.png")
        self.page.evaluate(
            "() => { const messages = document.getElementById('assistant-messages'); "
            "messages.scrollTop = messages.scrollHeight; }"
        )
        self._save_phase55_screenshot("operations-overview-mobile-bottom.png")

        with self.page.expect_navigation(wait_until="domcontentloaded"):
            inventory.locator(f'a[href="/products/{product_id}"]').click()
        self.assertRegex(self.page.url, rf"/products/{product_id}$")
        self.page.goto(BASE_URL + "/dashboard", wait_until="domcontentloaded")
        self.page.get_by_role("button", name="Hỏi trợ lý").click()
        self.page.locator("#assistant-input").fill("Tổng quan cần chú ý ở cửa hàng")
        self.page.locator("#assistant-input").press("Enter")
        purchasing = self.page.locator(".assistant-operations-overview section").nth(1)
        expect(purchasing.locator(f'a[href="/purchasing/{order_id}"]')).to_be_visible()
        with self.page.expect_navigation(wait_until="domcontentloaded"):
            purchasing.locator(f'a[href="/purchasing/{order_id}"]').click()
        self.assertRegex(self.page.url, rf"/purchasing/{order_id}$")
        self.page.goto(BASE_URL + "/dashboard", wait_until="domcontentloaded")
        self.page.get_by_role("button", name="Hỏi trợ lý").click()
        self.page.locator("#assistant-input").fill("Tổng quan cần chú ý ở cửa hàng")
        self.page.locator("#assistant-input").press("Enter")
        sales = self.page.locator(".assistant-operations-overview section").nth(2)
        report_link = sales.locator('a[href^="/reports/?start="]')
        expect(report_link).to_be_visible()
        with self.page.expect_navigation(wait_until="domcontentloaded") as navigation:
            report_link.click()
        self.assertEqual(navigation.value.status, 200)
        self.assertRegex(self.page.url, r"/reports/\?start=\d{4}-\d{2}-\d{2}&end=\d{4}-\d{2}-\d{2}$")
        expect(self.page.get_by_role("heading", name="Báo cáo", exact=True)).to_be_visible()
        self._assert_browser_diagnostics()

    def test_tenant_export_job_runs_and_downloads_in_isolated_storage(self):
        fixture = {"job_id": None, "audit_start_id": None}
        self.addCleanup(self._cleanup_export_fixture, fixture)
        self._login("admin")
        with get_connection() as connection:
            fixture["audit_start_id"] = fetch_one(
                connection, "SELECT COALESCE(MAX(id),0) maximum FROM audit_events"
            )["maximum"]
        self.page.goto(BASE_URL + "/users/export", wait_until="domcontentloaded")
        self.page.get_by_label("Mật khẩu hiện tại").fill(SEED_PASSWORDS["admin"])
        passphrase = f"phase43-{uuid4().hex}"
        self.page.get_by_label("Passphrase mã hóa").fill(passphrase)
        self.page.get_by_label("Xác nhận passphrase").fill(passphrase)
        self.page.get_by_role("button", name="Yêu cầu xuất dữ liệu").click()
        self.page.wait_for_url(re.compile(r"/users/export/jobs/\d+$"))
        fixture["job_id"] = int(self.page.url.rstrip("/").split("/")[-1])
        expect(self.page.get_by_role("heading", name="Yêu cầu đang chờ")).to_be_visible()
        expect(self.page.locator("[data-export-indicator]")).to_be_visible()
        expect(self.page.locator("#export-download")).to_be_hidden()
        status_response = self.page.request.get(BASE_URL + f"/users/export/jobs/{fixture['job_id']}/status")
        self.assertEqual(status_response.status, 200)
        self.assertEqual(status_response.json()["status"], "pending")
        widths = (320, 390, 768, 820, 1024, 1440)
        for width in widths:
            self.page.set_viewport_size({"width": width, "height": 900})
            self.page.goto(BASE_URL + f"/users/export/jobs/{fixture['job_id']}", wait_until="domcontentloaded")
            self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
            expect(self.page.locator("[data-export-indicator]")).to_be_visible()
            if width in (320, 1440):
                self._save_phase43_screenshot(f"operations-export-pending-{width}.png")

        # Fixed repository module and interpreter; the generated numeric fixture id is the
        # only argument derived from test data, and shell execution is disabled.
        worker = subprocess.run(  # nosec B603
            [sys.executable, "-m", "petcare.services.tenant_export_worker_cli",
             "--job-id", str(fixture["job_id"])],
            cwd=ROOT, env=os.environ.copy(), timeout=90,
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(worker.returncode, 0, "Isolated tenant-export worker failed.")
        with get_connection() as connection:
            job = fetch_one(
                connection, "SELECT status,artifact_key,artifact_size,passphrase_ciphertext,expires_at "
                "FROM tenant_export_jobs WHERE tenant_id=%s AND id=%s",
                (self.tenant_id, fixture["job_id"]),
            )
        self.assertEqual(job["status"], "ready")
        self.assertIsNone(job["passphrase_ciphertext"])
        self.assertGreater(job["artifact_size"], 0)
        self.assertIsNotNone(job["expires_at"])
        self.page.wait_for_function(
            """async () => {
              const node = document.querySelector('#export-download');
              return node && !node.hidden && node.href.includes('/download');
            }""",
            timeout=15000,
        )
        expect(self.page.locator("#export-download")).to_be_visible()
        self.page.reload(wait_until="domcontentloaded")
        expect(self.page.get_by_role("heading", name="Bản xuất đã sẵn sàng")).to_be_visible()
        for width in widths:
            self.page.set_viewport_size({"width": width, "height": 900})
            self.page.reload(wait_until="domcontentloaded")
            self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
            expect(self.page.locator("#export-download")).to_be_visible()
            if width in (320, 1440):
                if os.getenv("AXE_CORE_PATH"):
                    self._axe_audit(f"phase43-operations-export-ready-{width}")
                self._save_phase43_screenshot(f"operations-export-ready-{width}.png")
        with self.page.expect_download() as downloaded:
            self.page.locator("#export-download").click()
        download = downloaded.value
        self.assertTrue(download.suggested_filename.endswith(".pcarexport"))
        self.assertEqual(os.path.getsize(download.path()), job["artifact_size"])
        completed_download = [
            item for item in self.failed_requests
            if item["path"] == f"/users/export/jobs/{fixture['job_id']}/download"
            and item["failure"] == "net::ERR_ABORTED"
        ]
        self.assertEqual(len(completed_download), 1, "The browser download should be the only aborted navigation.")
        self.failed_requests[:] = [item for item in self.failed_requests if item not in completed_download]
        self._assert_browser_diagnostics()

    def test_pos_catalog_503_shows_retry_and_preserves_cart(self):
        self._login("admin")
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.goto(BASE_URL + "/invoices/new", wait_until="domcontentloaded")
        self.page.locator('button[data-pos-item]:not([disabled])').first.click()
        self.assertEqual(self.page.locator("#invoice-lines .invoice-line").count(), 1)
        search = self.page.locator("[data-pos-search]")
        endpoint = urlsplit(search.get_attribute("data-source")).path
        calls = {"count": 0}

        def fail_once(route):
            calls["count"] += 1
            if calls["count"] == 1:
                route.fulfill(status=503, json={"error": "temporary QA failure"})
            else:
                route.continue_()

        self.page.route(re.compile(re.escape(endpoint) + r".*"), fail_once)
        search.fill("phase43-retry-probe")
        expect(self.page.locator("[data-pos-status]")).to_contain_text("Không tải được danh mục")
        expect(self.page.locator("[data-pos-retry]")).to_be_visible()
        self.assertEqual(self.page.locator("#invoice-lines .invoice-line").count(), 1)
        self.page.locator("[data-pos-retry]").click()
        expect(self.page.locator("[data-pos-retry]")).to_be_hidden()
        expect(self.page.locator("[data-pos-status]")).not_to_contain_text("Không tải được danh mục")
        self.assertEqual(calls["count"], 2)
        self.assertEqual(self.page.locator("#invoice-lines .invoice-line").count(), 1)
        failed = [item for item in self.http_errors if item["path"] == endpoint and item["status"] == 503]
        self.assertEqual(len(failed), 1, "The injected QA 503 should be the only expected error response.")
        self.http_errors[:] = [item for item in self.http_errors if item not in failed]
        injected_console = [message for message in self.console_errors if "503 (Service Unavailable)" in message]
        self.assertEqual(len(injected_console), 1, "The injected QA 503 should produce one browser console notice.")
        self.console_errors[:] = [message for message in self.console_errors if message not in injected_console]
        self.page.unroute(re.compile(re.escape(endpoint) + r".*"), fail_once)
        if os.getenv("AXE_CORE_PATH"):
            self._axe_audit("phase43-pos-catalog-retry-mobile")
        self._save_phase43_screenshot("pos-catalog-retry-390.png")
        self._assert_browser_diagnostics()

    def test_customer_pet_workflow_and_responsive_navigation(self):
        """Exercise forms, paid-sale navigation, and responsive pages in QA MySQL."""
        fixture = {
            "customer_id": None, "pet_id": None, "invoice_id": None,
            "pet_ids": [], "invoice_ids": [],
        }
        self.addCleanup(self._cleanup_customer_pet_fixture, fixture)
        self._login("admin")
        suffix = uuid4().hex[:8].upper()
        customer_name = f"Phase 4 Buyer {suffix}"
        customer_phone = "09" + f"{uuid4().int % 100_000_000:08d}"
        pet_code = f"P4-{suffix}"
        pet_name = f"Luna {suffix[:4]}"

        self.page.set_viewport_size({"width": 1440, "height": 960})
        self.page.goto(BASE_URL + "/customers/new", wait_until="domcontentloaded")
        self.page.locator("#full_name").fill(customer_name)
        self.page.locator("#phone").fill("123")
        self.page.get_by_role("button", name="Tạo khách hàng").click()
        expect(self.page.locator("#phone")).to_have_attribute("aria-invalid", "true")
        expect(self.page.locator("#phone-error")).to_contain_text("8 đến 15 chữ số")
        self.assertEqual(self.page.locator("#full_name").input_value(), customer_name)
        self._save_page_screenshot("customer-form-invalid-1440.png")

        self.page.locator("#phone").fill(customer_phone)
        self.page.locator("#address").fill("QA only · isolated browser workflow")
        self.page.get_by_role("button", name="Tạo khách hàng").click()
        self.page.wait_for_url(BASE_URL + "/customers/")
        expect(self.page.locator(".flash-success")).to_contain_text("Đã thêm khách hàng")
        self.page.locator('.search-form input[name="q"]').fill(customer_name)
        self.page.locator('.search-form button[type="submit"]').click()
        customer_detail_path = self.page.locator(".customer-name-link").first.get_attribute("href")
        self.assertIsNotNone(customer_detail_path)
        fixture["customer_id"] = int(customer_detail_path.rstrip("/").split("/")[-1])

        self.page.goto(
            BASE_URL + f"/customers/{fixture['customer_id']}/edit",
            wait_until="domcontentloaded",
        )
        self.page.locator("#address").fill("QA only · edited browser workflow")
        self._save_page_screenshot("customer-form-edit-1440.png")
        self.page.get_by_role("button", name="Lưu thay đổi").click()
        self.page.wait_for_url(BASE_URL + "/customers/")
        expect(self.page.locator(".flash-success")).to_contain_text("Đã cập nhật khách hàng")

        self.page.goto(BASE_URL + "/pets/new", wait_until="domcontentloaded")
        self.page.locator('input[name="code"]').fill(pet_code)
        self.page.locator('input[name="name"]').fill(pet_name)
        self.page.locator('input[name="species"]').fill("Mèo")
        self.page.locator('input[name="breed"]').fill("Mèo ta")
        weight = self.page.locator('input[name="weight_kg"]')
        weight.fill("0")
        self.page.locator('input[name="sale_price"]').fill("100000")
        self.assertTrue(weight.evaluate("element => element.validity.rangeUnderflow"))
        self._save_page_screenshot("pet-form-invalid-1440.png")
        self.page.get_by_role("button", name="Thêm thú cưng").click()
        self.assertTrue(self.page.url.endswith("/pets/new"))
        self.assertEqual(self.page.evaluate("document.activeElement.name"), "weight_kg")
        weight.fill("")
        self._save_page_screenshot("pet-form-new-1440.png")
        self.page.get_by_role("button", name="Thêm thú cưng").click()
        self.page.wait_for_url(BASE_URL + "/pets/")
        expect(self.page.locator(".flash-success")).to_contain_text("Đã thêm cá thể thú cưng")
        self.page.locator('.search-form input[name="q"]').fill(pet_code)
        self.page.locator('.search-form button[type="submit"]').click()
        pet_detail_path = self.page.locator(".pet-card a[aria-label]").first.get_attribute("href")
        self.assertIsNotNone(pet_detail_path)
        fixture["pet_id"] = int(pet_detail_path.rstrip("/").split("/")[-1])

        self.page.goto(BASE_URL + f"/pets/{fixture['pet_id']}/edit", wait_until="domcontentloaded")
        self.page.locator('input[name="coat_color"]').fill("Trắng · QA")
        self._save_page_screenshot("pet-form-edit-1440.png")
        self.page.get_by_role("button", name="Lưu thay đổi").click()
        self.page.wait_for_url(BASE_URL + f"/pets/{fixture['pet_id']}")
        expect(self.page.get_by_text("Trắng · QA")).to_be_visible()

        for width in (320, 390, 768, 820, 1440):
            height = 900 if width < 600 else 1024
            self.page.set_viewport_size({"width": width, "height": height})
            self.page.goto(BASE_URL + "/dashboard", wait_until="domcontentloaded")
            self.assertEqual(
                self.page.evaluate("document.documentElement.scrollWidth"), width,
                f"Shared shell overflows at {width}px.",
            )
            self._accessibility_smoke()
            self._save_page_screenshot(f"dashboard-{width}.png")

            self.page.goto(BASE_URL + "/customers/", wait_until="domcontentloaded")
            self.page.locator('.search-form input[name="q"]').fill(customer_name)
            self.page.locator('.search-form button[type="submit"]').click()
            customer_result = self.page.locator(
                ".customer-mobile-card .customer-name-link" if width <= 680
                else ".customer-table-scroll .customer-name-link"
            ).first
            expect(customer_result).to_be_visible()
            customer_document_width = self.page.evaluate("document.documentElement.scrollWidth")
            customer_overflow = self.page.evaluate("""() => [...document.querySelectorAll('body *')]
              .filter(node => getComputedStyle(node).display !== 'none' &&
                node.getBoundingClientRect().right > innerWidth + 1)
              .map(node => ({tag: node.tagName, className: typeof node.className === 'string' ? node.className : '',
                right: Math.round(node.getBoundingClientRect().right), text: (node.innerText || '').slice(0, 45)}))
              .slice(0, 8)""")
            self.assertEqual(
                customer_document_width, width,
                f"Customer list overflows at {width}px: {customer_overflow}",
            )
            if width <= 680:
                expect(self.page.locator(".customer-mobile-list")).to_be_visible()
                expect(self.page.locator(".customer-mobile-card").first).to_be_visible()
                expect(self.page.locator(".customer-table-scroll")).to_be_hidden()
                mobile_action_overlap = self.page.evaluate("""() => {
                  const launcher = document.querySelector('#assistant-launcher');
                  const buttonRects = [...document.querySelectorAll('.customer-mobile-actions a, .customer-mobile-actions button')]
                    .map(button => button.getBoundingClientRect());
                  if (!launcher || getComputedStyle(launcher).display === 'none') return false;
                  const fixed = launcher.getBoundingClientRect();
                  return buttonRects.some(button => button.left < fixed.right && button.right > fixed.left &&
                    button.top < fixed.bottom && button.bottom > fixed.top);
                }""")
                self.assertFalse(
                    mobile_action_overlap,
                    f"Floating assistant overlaps customer actions at {width}px.",
                )
            else:
                expect(self.page.locator(".customer-table-scroll")).to_be_visible()
                expect(self.page.locator(".customer-mobile-list")).to_be_hidden()
            self._accessibility_smoke()
            self._save_page_screenshot(f"customers-list-{width}.png")

            self.page.goto(BASE_URL + "/pets/", wait_until="domcontentloaded")
            self.page.locator('.search-form input[name="q"]').fill(pet_code)
            self.page.locator('.search-form button[type="submit"]').click()
            self.assertEqual(
                self.page.evaluate("document.documentElement.scrollWidth"), width,
                f"Pet list overflows at {width}px.",
            )
            self._accessibility_smoke()
            self._save_page_screenshot(f"pets-list-{width}.png")

        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.goto(
            BASE_URL + f"/invoices/new?customer_id={fixture['customer_id']}",
            wait_until="domcontentloaded",
        )
        self.assertEqual(self.page.locator("#customer_id").input_value(), str(fixture["customer_id"]))
        self.page.locator('[data-pos-filter="pet"]').click()
        self.page.locator("[data-pos-search]").fill(pet_code)
        pet_card = self.page.locator(
            f'button[data-pos-item][data-selection="pet:{fixture["pet_id"]}"]'
        )
        expect(pet_card).to_be_visible()
        pet_card.click()
        expect(self.page.locator("[data-pos-mobile-count]")).to_contain_text("1")
        self.page.locator("#invoice-submit").click()
        self.page.wait_for_url(re.compile(r"/invoices/\d+$"))
        fixture["invoice_id"] = int(self.page.url.rstrip("/").split("/")[-1])
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.get_by_role("button", name="Xác nhận thanh toán").click()
        expect(self.page.locator(".flash-success")).to_contain_text("Thanh toán thành công")

        fixture["pet_ids"].append(fixture["pet_id"])
        fixture["invoice_ids"].append(fixture["invoice_id"])
        extra_pet_ids = []
        for index in range(12):
            extra_pet_ids.append(pet_service.create_pet(
                self.admin_id,
                {
                    "code": f"{pet_code}-{index + 1:02d}",
                    "name": f"{pet_name} {index + 1:02d}",
                    "species": "Mèo",
                    "breed": "Mèo ta",
                    "sale_price": "100000",
                },
                tenant_id=self.tenant_id,
            ))
        extra_invoice_id = invoice_service.create_invoice(
            self.admin_id,
            {"customer_id": str(fixture["customer_id"]), "note": "QA 13-pet pagination"},
            [
                {"item_type": "pet", "item_id": str(pet_id), "quantity": "1"}
                for pet_id in extra_pet_ids
            ],
            tenant_id=self.tenant_id,
        )
        fixture["invoice_ids"].append(extra_invoice_id)
        invoice_service.pay_invoice(
            self.admin_id, extra_invoice_id, tenant_id=self.tenant_id
        )
        fixture["pet_ids"].extend(extra_pet_ids)

        for width in (320, 390, 768, 820, 1024, 1440):
            self.page.set_viewport_size({"width": width, "height": 900 if width < 600 else 1024})
            self.page.goto(
                BASE_URL + f"/customers/{fixture['customer_id']}",
                wait_until="domcontentloaded",
            )
            self.assertEqual(
                self.page.evaluate("document.documentElement.scrollWidth"), width,
                f"Customer detail overflows at {width}px.",
            )
            expect(self.page.locator(".customer-pet-link")).to_have_count(12)
            expect(self.page.locator(".customer-pets-pagination")).to_contain_text(
                "13 thú cưng"
            )
            if width == 320:
                pet_next = self.page.locator(".customer-pets-pagination a[rel='next']")
                pet_next.focus()
                self.page.keyboard.press("Tab")
                self.page.keyboard.press("Shift+Tab")
                focus_state = pet_next.evaluate("""element => ({
                  active: document.activeElement === element,
                  visible: element.matches(':focus-visible'),
                  outline: getComputedStyle(element).outlineStyle,
                  width: getComputedStyle(element).outlineWidth
                })""")
                self.assertTrue(
                    focus_state["active"] and focus_state["visible"]
                    and focus_state["outline"] != "none",
                    f"Purchased-pet pagination lacks visible keyboard focus: {focus_state}",
                )
                self._axe_audit("customer-detail-13-pets-page-1-mobile")
                pet_next.click()
                self.page.wait_for_url("**pet_page=2")
                expect(self.page.locator(".customer-pet-link")).to_have_count(1)
                expect(self.page.locator(".customer-pet-link")).to_contain_text(pet_name)
                expect(self.page.locator(".customer-pets-pagination a[rel='prev']")).to_be_visible()
                self._axe_audit("customer-detail-13-pets-page-2-mobile")
                self._save_page_screenshot("customer-detail-purchased-pets-page-2-320.png")
                self.page.goto(BASE_URL + f"/customers/{fixture['customer_id']}")
            elif width == 1440:
                self._axe_audit("customer-detail-13-pets-desktop")
            self._accessibility_smoke()
            self._save_page_screenshot(f"customer-detail-purchased-pet-{width}.png")

            self.page.goto(
                BASE_URL + f"/pets/{fixture['pet_id']}", wait_until="domcontentloaded"
            )
            self.assertEqual(
                self.page.evaluate("document.documentElement.scrollWidth"), width,
                f"Pet detail overflows at {width}px.",
            )
            expect(self.page.locator(".customer-record-link")).to_have_attribute(
                "href", f"/customers/{fixture['customer_id']}"
            )
            self._accessibility_smoke()
            self._save_page_screenshot(f"pet-detail-buyer-{width}.png")
        self.page.set_viewport_size({"width": 720, "height": 900})
        self.page.goto(BASE_URL + f"/customers/{fixture['customer_id']}", wait_until="domcontentloaded")
        self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), 720)
        self._save_page_screenshot("customer-detail-zoom-200-equivalent-720.png")
        self._assert_browser_diagnostics()

    def test_product_inventory_to_pos_checkout_workflow(self):
        fixture = {"product_id": None, "invoice_id": None}
        self.addCleanup(self._cleanup_product_invoice_fixture, fixture)
        self._login("admin")
        suffix = uuid4().hex[:8].upper()
        code = f"P42-{suffix}"
        name = f"QA POS item {suffix}"
        fixture["code"] = code

        self.page.set_viewport_size({"width": 1440, "height": 960})
        self.page.goto(BASE_URL + "/products/new", wait_until="domcontentloaded")
        self.page.locator('input[name="code"]').fill(code)
        self.page.locator('input[name="name"]').fill(name)
        self.page.locator('input[name="category"]').fill("QA")
        self.page.locator('input[name="unit_price"]').fill("125000")
        self.page.locator('input[name="reorder_level"]').fill("2")
        stock_input = self.page.locator('input[name="stock_qty"]')
        stock_input.fill("-1")
        self.assertTrue(stock_input.evaluate("element => element.validity.rangeUnderflow"))
        self._axe_audit("product-create-invalid-desktop")
        self._save_page_screenshot("product-create-invalid-stock-1440.png")
        stock_input.fill("2")
        self.page.get_by_role("button", name="Tạo sản phẩm").click()
        self.page.wait_for_url(BASE_URL + "/products/")
        expect(self.page.locator(".flash-success")).to_contain_text("Đã tạo sản phẩm")
        self.page.locator('.search-form input[name="q"]').fill(code)
        self.page.locator('.search-form button[type="submit"]').click()
        product_href = self.page.locator(".product-list-table tbody tr a").first.get_attribute("href")
        self.assertIsNotNone(product_href)
        fixture["product_id"] = int(product_href.rstrip("/").split("/")[-1])

        self.page.goto(BASE_URL + f"/products/{fixture['product_id']}/edit", wait_until="domcontentloaded")
        self._axe_audit("product-inventory-adjustment-desktop")
        quantity = self.page.get_by_label("Số lượng thay đổi")
        reason = self.page.get_by_label("Lý do")
        quantity.fill("-3")
        reason.fill("QA negative stock rejection")
        self.page.get_by_role("button", name="Ghi điều chỉnh").click()
        expect(self.page.locator(".flash-error")).to_contain_text("tồn kho âm")
        with get_connection() as connection:
            before_adjustment = fetch_one(
                connection,
                "SELECT stock_qty FROM products WHERE tenant_id = %s AND id = %s",
                (self.tenant_id, fixture["product_id"]),
            )
        self.assertEqual(before_adjustment["stock_qty"], 2)

        self.page.get_by_label("Số lượng thay đổi").fill("1")
        self.page.get_by_label("Lý do").fill("QA stock count correction")
        self.page.get_by_role("button", name="Ghi điều chỉnh").click()
        expect(self.page.locator(".flash-success")).to_contain_text("Đã ghi nhận điều chỉnh tồn kho")
        self.page.locator('input[name="unit_price"]').fill("130000")
        self.page.get_by_role("button", name="Lưu thay đổi").click()
        self.page.wait_for_url(BASE_URL + "/products/")

        with get_connection() as connection:
            customer = fetch_one(
                connection,
                "SELECT id FROM customers WHERE tenant_id = %s AND active = 1 ORDER BY id LIMIT 1",
                (self.tenant_id,),
            )
        self.assertIsNotNone(customer, "QA seed must provide an active checkout customer.")
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.goto(BASE_URL + "/invoices/new", wait_until="domcontentloaded")
        search = self.page.locator("[data-pos-search]")
        search.fill("no-such-phase42-item")
        expect(self.page.locator("[data-pos-empty]")).to_be_visible()
        self._axe_audit("pos-search-empty-mobile")
        search.fill(code)
        product_card = self.page.locator(f'button[data-pos-item][data-code="{code}"]')
        expect(product_card).to_be_visible()
        self.page.get_by_label("Chọn khách hàng").select_option(str(customer["id"]))
        product_card.focus()
        self.assertTrue(product_card.evaluate("element => document.activeElement === element"))
        self.page.keyboard.press("Enter")
        self._axe_audit("pos-cart-mobile")
        expect(self.page.locator("[data-pos-mobile-count]")).to_contain_text("1")
        self.assertTrue(
            self.page.locator('.invoice-line input[name="quantity"]').last.evaluate(
                "element => document.activeElement === element"
            ),
            "Keyboard selection should move focus to the quantity control for the new cart row.",
        )
        expect(self.page.locator("[data-pos-mobile-total]")).to_have_text(
            self.page.locator("#estimate").inner_text()
        )
        self.page.locator('.invoice-line input[name="quantity"]').last.fill("4")
        quantity = self.page.locator('.invoice-line input[name="quantity"]').last
        self.assertTrue(quantity.evaluate("element => element.validity.rangeOverflow"))
        self.page.locator("#invoice-form").evaluate("form => { form.noValidate = true; }")
        self.page.get_by_role("button", name="Tạo hóa đơn").click()
        expect(self.page).to_have_url(re.compile(r"/invoices/new$"))
        expect(self.page.locator('#quantity_0[aria-invalid="true"]')).to_be_visible()
        expect(self.page.locator("#quantity_0-error")).to_contain_text("Tồn hiện tại")

        self.page.locator('#quantity_0').fill("2")
        self.page.get_by_role("button", name="Tạo hóa đơn").click()
        self.page.wait_for_url(re.compile(r"/invoices/\d+$"))
        fixture["invoice_id"] = int(self.page.url.rstrip("/").split("/")[-1])
        expect(self.page.locator(".invoice-detail-page")).to_contain_text(name)
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.get_by_role("button", name="Xác nhận thanh toán").click()
        expect(self.page.locator(".flash-success")).to_contain_text("Thanh toán thành công")
        self.assertEqual(
            invoice_service.pay_invoice(
                self.admin_id, fixture["invoice_id"], tenant_id=self.tenant_id
            ),
            "already_paid",
        )
        with get_connection() as connection:
            final_stock = fetch_one(
                connection,
                "SELECT stock_qty FROM products WHERE tenant_id = %s AND id = %s",
                (self.tenant_id, fixture["product_id"]),
            )["stock_qty"]
            sale_movement = fetch_one(
                connection,
                "SELECT quantity_delta FROM stock_movements "
                "WHERE tenant_id = %s AND product_id = %s AND invoice_id = %s",
                (self.tenant_id, fixture["product_id"], fixture["invoice_id"]),
            )
        self.assertEqual(final_stock, 1)
        self.assertEqual(sale_movement["quantity_delta"], -2)

        for width in (320, 390, 768, 820, 1024, 1440):
            self.page.set_viewport_size({"width": width, "height": 900 if width < 600 else 1024})
            self.page.goto(BASE_URL + f"/products/?q={code}", wait_until="domcontentloaded")
            self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
            expect(self.page.locator(".product-list-table tbody tr")).to_have_count(1)
            expect(self.page.locator(".product-list-table tbody tr")).to_contain_text("130.000")
            if width <= 680:
                expect(self.page.locator('.product-list-table td[data-label="Tồn kho"]')).to_be_visible()
                expect(self.page.locator('.product-list-table td[data-label="Trạng thái"]')).to_be_visible()
            if width == 320 or width == 1440:
                self._axe_audit(f"product-list-{width}")
            self._save_page_screenshot(f"products-list-after-{width}.png")

            self.page.goto(BASE_URL + "/invoices/new", wait_until="domcontentloaded")
            self.page.locator("[data-pos-search]").fill(code)
            card = self.page.locator(f'button[data-pos-item][data-code="{code}"]')
            expect(card).to_be_visible()
            card.click()
            self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
            if width <= 680:
                expect(self.page.locator(".pos-mobile-cart")).to_be_visible()
                expect(self.page.locator("[data-pos-mobile-count]")).to_contain_text("1")
            if width == 1440:
                self._axe_audit("pos-cart-desktop")
            self._save_page_screenshot(f"pos-after-{width}.png")

        self.page.set_viewport_size({"width": 320, "height": 900})
        self.page.goto(BASE_URL + f"/products/{fixture['product_id']}", wait_until="domcontentloaded")
        self._axe_audit("product-detail-mobile")
        self._save_page_screenshot("product-detail-after-320.png")
        self.page.set_viewport_size({"width": 1440, "height": 960})
        self.page.goto(BASE_URL + "/products/new", wait_until="domcontentloaded")
        self._axe_audit("product-create-desktop")
        self._save_page_screenshot("product-create-after-1440.png")
        self.page.goto(BASE_URL + f"/products/{fixture['product_id']}/edit", wait_until="domcontentloaded")
        self._axe_audit("product-edit-inventory-desktop")
        self._save_page_screenshot("product-edit-stock-history-after-1440.png")

        self.page.set_viewport_size({"width": 720, "height": 900})
        self.page.goto(BASE_URL + f"/products/?q={code}", wait_until="domcontentloaded")
        self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), 720)
        self._save_page_screenshot("products-list-zoom-200-equivalent-720.png")
        self.page.goto(BASE_URL + "/invoices/new", wait_until="domcontentloaded")
        self.page.locator("[data-pos-search]").fill(code)
        expect(self.page.locator(f'button[data-pos-item][data-code="{code}"]')).to_be_visible()
        self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), 720)
        self._save_page_screenshot("pos-zoom-200-equivalent-720.png")
        self._assert_browser_diagnostics()

    def test_staff_can_deactivate_and_reactivate_customer(self):
        fixture = {"customer_id": None, "pet_id": None, "invoice_id": None}
        self.addCleanup(self._cleanup_customer_pet_fixture, fixture)
        suffix = uuid4().hex[:8].upper()
        customer_name = f"Phase 42 Status {suffix}"
        fixture["customer_id"] = customer_service.create_customer(
            self.admin_id,
            {
                "full_name": customer_name,
                "phone": "09" + f"{uuid4().int % 100_000_000:08d}",
                "address": "Synthetic browser permission fixture",
            },
            tenant_id=self.tenant_id,
        )
        self._login("staff1")
        self.page.set_viewport_size({"width": 1440, "height": 960})

        def customer_row():
            self.page.goto(
                BASE_URL + f"/customers/?all=1&q={customer_name}",
                wait_until="domcontentloaded",
            )
            return self.page.locator(".customer-table-scroll tbody tr").filter(
                has_text=customer_name
            )

        row = customer_row()
        expect(row.locator(".status-active")).to_be_visible()
        self.page.once("dialog", lambda dialog: dialog.accept())
        row.get_by_role("button", name="Ngừng").click()
        self.page.wait_for_url(BASE_URL + "/customers/?all=1")
        row = customer_row()
        expect(row.locator(".status-muted")).to_be_visible()
        row.get_by_role("button", name="Kích hoạt").click()
        self.page.wait_for_url(BASE_URL + "/customers/?all=1")
        row = customer_row()
        expect(row.locator(".status-active")).to_be_visible()
        self._assert_browser_diagnostics()

    def _cleanup_product_invoice_fixture(self, fixture):
        product_id = fixture.get("product_id")
        invoice_id = fixture.get("invoice_id")
        if not product_id and fixture.get("code"):
            with get_connection() as connection:
                product = fetch_one(
                    connection,
                    "SELECT id FROM products WHERE tenant_id = %s AND code = %s",
                    (self.tenant_id, fixture["code"]),
                )
            product_id = product["id"] if product else None
        if not product_id and not invoice_id:
            return
        with transaction() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SET @petcare_tenant_id = %s", (self.tenant_id,))
                for entity_type, entity_id in (("invoice", invoice_id), ("product", product_id)):
                    if entity_id:
                        cursor.execute(
                            "DELETE FROM audit_events WHERE tenant_id = %s "
                            "AND entity_type = %s AND entity_id = %s",
                            (self.tenant_id, entity_type, entity_id),
                        )
                if invoice_id:
                    cursor.execute(
                        "DELETE FROM stock_movements WHERE tenant_id = %s AND invoice_id = %s",
                        (self.tenant_id, invoice_id),
                    )
                    cursor.execute(
                        "DELETE FROM invoice_items WHERE tenant_id = %s AND invoice_id = %s",
                        (self.tenant_id, invoice_id),
                    )
                    cursor.execute(
                        "DELETE FROM invoices WHERE tenant_id = %s AND id = %s",
                        (self.tenant_id, invoice_id),
                    )
                if product_id:
                    cursor.execute(
                        "DELETE FROM stock_movements WHERE tenant_id = %s AND product_id = %s",
                        (self.tenant_id, product_id),
                    )
                    cursor.execute(
                        "DELETE FROM products WHERE tenant_id = %s AND id = %s",
                        (self.tenant_id, product_id),
                    )
            finally:
                cursor.close()

    def _cleanup_purchase_fixture(self, fixture):
        order_ids = set(fixture.get("order_ids", ()))
        product_ids = set(fixture.get("product_ids", ()))
        if fixture.get("product_id"):
            product_ids.add(fixture["product_id"])
        supplier_id = fixture.get("supplier_id")
        if not order_ids and not product_ids and not supplier_id:
            return
        with transaction() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SET @petcare_tenant_id = %s", (self.tenant_id,))
                for order_id in order_ids:
                    cursor.execute(
                        "DELETE FROM audit_events WHERE tenant_id=%s AND entity_type='purchase_order' AND entity_id=%s",
                        (self.tenant_id, order_id),
                    )
                    cursor.execute(
                        "DELETE FROM stock_movements WHERE tenant_id=%s AND purchase_order_id=%s",
                        (self.tenant_id, order_id),
                    )
                    cursor.execute(
                        "DELETE FROM purchase_order_receipt_requests WHERE tenant_id=%s AND purchase_order_id=%s",
                        (self.tenant_id, order_id),
                    )
                    cursor.execute(
                        "DELETE FROM purchase_order_items WHERE tenant_id=%s AND purchase_order_id=%s",
                        (self.tenant_id, order_id),
                    )
                    cursor.execute(
                        "DELETE FROM purchase_orders WHERE tenant_id=%s AND id=%s",
                        (self.tenant_id, order_id),
                    )
                for product_id in product_ids:
                    cursor.execute(
                        "DELETE FROM audit_events WHERE tenant_id=%s AND entity_type='product' AND entity_id=%s",
                        (self.tenant_id, product_id),
                    )
                    cursor.execute(
                        "DELETE FROM stock_movements WHERE tenant_id=%s AND product_id=%s",
                        (self.tenant_id, product_id),
                    )
                    cursor.execute(
                        "DELETE FROM products WHERE tenant_id=%s AND id=%s",
                        (self.tenant_id, product_id),
                    )
                if supplier_id:
                    cursor.execute(
                        "DELETE FROM audit_events WHERE tenant_id=%s AND entity_type='supplier' AND entity_id=%s",
                        (self.tenant_id, supplier_id),
                    )
                    cursor.execute(
                        "DELETE FROM suppliers WHERE tenant_id=%s AND id=%s",
                        (self.tenant_id, supplier_id),
                    )
            finally:
                cursor.close()

    def _cleanup_export_fixture(self, fixture):
        job_id = fixture.get("job_id")
        if not job_id:
            return
        with get_connection() as connection:
            row = fetch_one(
                connection,
                "SELECT artifact_key FROM tenant_export_jobs WHERE tenant_id=%s AND id=%s",
                (self.tenant_id, job_id),
            )
        if row and row.get("artifact_key"):
            qa_storage = get_export_storage({
                "TENANT_EXPORT_STORAGE_BACKEND": "local",
                "TENANT_EXPORT_DIR": os.environ["TENANT_EXPORT_DIR"],
            })
            qa_storage.delete(row["artifact_key"])
        with transaction() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SET @petcare_tenant_id = %s", (self.tenant_id,))
                if fixture.get("audit_start_id") is not None:
                    cursor.execute(
                        "DELETE FROM audit_events WHERE id>%s AND tenant_id=%s "
                        "AND event_type='tenant.exported' AND entity_type='tenant' AND entity_id=%s",
                        (fixture["audit_start_id"], self.tenant_id, self.tenant_id),
                    )
                cursor.execute(
                    "DELETE FROM tenant_export_jobs WHERE tenant_id=%s AND id=%s",
                    (self.tenant_id, job_id),
                )
            finally:
                cursor.close()

    def _cleanup_customer_pet_fixture(self, fixture):
        customer_id = fixture["customer_id"]
        pet_ids = set(fixture.get("pet_ids", ()))
        invoice_ids = set(fixture.get("invoice_ids", ()))
        if fixture.get("pet_id"):
            pet_ids.add(fixture["pet_id"])
        if fixture.get("invoice_id"):
            invoice_ids.add(fixture["invoice_id"])
        if not customer_id and not pet_ids and not invoice_ids:
            return
        with transaction() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SET @petcare_tenant_id = %s", (self.tenant_id,))
                entities = [("invoice", invoice_id) for invoice_id in invoice_ids]
                entities.extend(("pet", pet_id) for pet_id in pet_ids)
                if customer_id:
                    entities.append(("customer", customer_id))
                for entity_type, entity_id in entities:
                    if entity_id:
                        cursor.execute(
                            "DELETE FROM audit_events WHERE tenant_id = %s "
                            "AND entity_type = %s AND entity_id = %s",
                            (self.tenant_id, entity_type, entity_id),
                        )
                for invoice_id in invoice_ids:
                    cursor.execute("DELETE FROM invoice_items WHERE tenant_id = %s AND invoice_id = %s", (self.tenant_id, invoice_id))
                    cursor.execute("DELETE FROM invoices WHERE tenant_id = %s AND id = %s", (self.tenant_id, invoice_id))
                for pet_id in pet_ids:
                    cursor.execute("DELETE FROM pet_photo_lsh WHERE tenant_id = %s AND pet_id = %s", (self.tenant_id, pet_id))
                    cursor.execute("DELETE FROM pets WHERE tenant_id = %s AND id = %s", (self.tenant_id, pet_id))
                if customer_id:
                    cursor.execute("DELETE FROM customers WHERE tenant_id = %s AND id = %s", (self.tenant_id, customer_id))
            finally:
                cursor.close()

    def _create_paid_refund_fixture(self, fixture):
        suffix = uuid4().hex[:10].upper()
        fixture["customer_id"] = customer_service.create_customer(
            self.admin_id,
            {
                "full_name": f"Browser refund QA {suffix}",
                "phone": "09" + f"{uuid4().int % 100_000_000:08d}",
                "address": "Synthetic Playwright fixture",
            },
        )
        for code_suffix, opening_stock in (("A", 5), ("B", 4)):
            product_id = product_service.create_product(
                self.admin_id,
                {
                    "code": f"PW-{suffix}-{code_suffix}",
                    "name": f"Refund QA {suffix} {code_suffix}",
                    "category": "QA",
                    "unit_price": "100000",
                    "stock_qty": str(opening_stock),
                    "reorder_level": "0",
                },
            )
            fixture["products"].append((product_id, opening_stock))
        fixture["invoice_id"] = invoice_service.create_invoice(
            self.admin_id,
            {
                "customer_id": str(fixture["customer_id"]),
                "note": f"Playwright refund fixture {suffix}",
            },
            [
                {"item_type": "product", "item_id": str(product_id), "quantity": "2"}
                for product_id, _opening_stock in fixture["products"]
            ],
        )
        invoice_service.pay_invoice(self.admin_id, fixture["invoice_id"])
        invoice = invoice_service.get_invoice(self.admin_id, fixture["invoice_id"])
        line_ids = {
            item["product_id"]: item["id"] for item in invoice["items"]
        }
        return line_ids

    def _refund_snapshot(self, invoice_id, products):
        with get_connection() as connection:
            invoice = fetch_one(
                connection, "SELECT status FROM invoices WHERE id = %s", (invoice_id,)
            )
            refund = fetch_one(
                connection,
                "SELECT COUNT(*) AS count, COALESCE(SUM(refund_total), 0) AS total "
                "FROM invoice_refunds WHERE invoice_id = %s",
                (invoice_id,),
            )
            refund_lines = fetch_one(
                connection,
                "SELECT COALESCE(SUM(quantity), 0) AS quantity "
                "FROM invoice_refund_items WHERE invoice_id = %s",
                (invoice_id,),
            )
            movement = fetch_one(
                connection,
                "SELECT COUNT(*) AS count, COALESCE(SUM(quantity_delta), 0) AS quantity "
                "FROM stock_movements WHERE invoice_id = %s AND refund_id IS NOT NULL",
                (invoice_id,),
            )
            stocks = {
                product_id: fetch_one(
                    connection, "SELECT stock_qty FROM products WHERE id = %s", (product_id,)
                )["stock_qty"]
                for product_id, _opening_stock in products
            }
        return {
            "status": invoice["status"],
            "refund_count": refund["count"],
            "refund_total": Decimal(refund["total"]),
            "refunded_quantity": refund_lines["quantity"],
            "movement_count": movement["count"],
            "movement_quantity": movement["quantity"],
            "stocks": stocks,
        }

    def _cleanup_refund_fixture(self, fixture):
        customer_id = fixture["customer_id"]
        products = fixture["products"]
        invoice_id = fixture["invoice_id"]
        product_ids = [product_id for product_id, _stock in products]
        if not customer_id and not product_ids and not invoice_id:
            return
        with transaction() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SET @petcare_tenant_id = %s", (self.tenant_id,))
                if invoice_id:
                    cursor.execute(
                        "SELECT id FROM invoice_refunds WHERE invoice_id = %s", (invoice_id,)
                    )
                    refund_ids = [row[0] for row in cursor.fetchall()]
                    cursor.execute(
                        "DELETE FROM audit_events WHERE entity_type = 'invoice' AND entity_id = %s",
                        (invoice_id,),
                    )
                    for refund_id in refund_ids:
                        cursor.execute(
                            "DELETE FROM audit_events "
                            "WHERE entity_type = 'invoice_refund' AND entity_id = %s",
                            (refund_id,),
                        )
                    cursor.execute("DELETE FROM stock_movements WHERE invoice_id = %s", (invoice_id,))
                    cursor.execute("DELETE FROM invoice_refund_items WHERE invoice_id = %s", (invoice_id,))
                    cursor.execute("DELETE FROM invoice_refunds WHERE invoice_id = %s", (invoice_id,))
                    cursor.execute("DELETE FROM invoice_items WHERE invoice_id = %s", (invoice_id,))
                    cursor.execute("DELETE FROM invoices WHERE id = %s", (invoice_id,))
                if product_ids:
                    for product_id in product_ids:
                        cursor.execute(
                            "DELETE FROM audit_events "
                            "WHERE entity_type = 'product' AND entity_id = %s",
                            (product_id,),
                        )
                        cursor.execute(
                            "DELETE FROM stock_movements WHERE product_id = %s", (product_id,)
                        )
                        cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
                if customer_id:
                    cursor.execute(
                        "DELETE FROM audit_events WHERE entity_type = 'customer' AND entity_id = %s",
                        (customer_id,),
                    )
                    cursor.execute("DELETE FROM customers WHERE id = %s", (customer_id,))
            finally:
                cursor.close()

    def test_browser_refund_confirmation_validation_idempotency_and_persistence(self):
        fixture = {"customer_id": None, "products": [], "invoice_id": None}
        self.addCleanup(self._cleanup_refund_fixture, fixture)
        line_ids = self._create_paid_refund_fixture(fixture)
        customer_id = fixture["customer_id"]
        products = fixture["products"]
        invoice_id = fixture["invoice_id"]
        self._login("admin")
        response = self.page.goto(BASE_URL + f"/invoices/{invoice_id}", wait_until="domcontentloaded")
        self.assertEqual(response.status, 200)
        form = self.page.locator(".refund-form")
        expect(form).to_be_visible()
        item_a = line_ids[products[0][0]]
        item_b = line_ids[products[1][0]]
        quantity_a = self.page.locator(f'input[name="quantity_{item_a}"]')
        quantity_b = self.page.locator(f'input[name="quantity_{item_b}"]')

        before = self._refund_snapshot(invoice_id, products)
        quantity_a.fill("1")
        dialogs = []
        self.page.once("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
        form.locator('button[type="submit"]').click()
        self.assertEqual(len(dialogs), 1, "Cancel path must invoke the native confirmation dialog.")
        self.assertEqual(len(self.refund_posts), 0, "Dismissed confirmation must not POST a refund.")
        self.assertEqual(self._refund_snapshot(invoice_id, products), before)

        quantity_a = self.page.locator(f'input[name="quantity_{item_a}"]')
        quantity_a.fill("0")
        self.page.once("dialog", lambda dialog: dialog.accept())
        form.locator('button[type="submit"]').click()
        expect(self.page.locator(".flash-error")).to_contain_text("Số lượng hoàn phải lớn hơn 0")
        self.assertEqual(self._refund_snapshot(invoice_id, products), before)

        quantity_a = self.page.locator(f'input[name="quantity_{item_a}"]')
        quantity_a.evaluate("element => element.max = '3'")
        quantity_a.fill("3")
        self.page.once("dialog", lambda dialog: dialog.accept())
        form.locator('button[type="submit"]').click()
        expect(self.page.locator(".flash-error")).to_contain_text("vượt số còn có thể hoàn")
        self.assertEqual(self._refund_snapshot(invoice_id, products), before)

        partial_key = str(uuid4())
        quantity_a = self.page.locator(f'input[name="quantity_{item_a}"]')
        quantity_a.fill("1")
        self.page.locator('input[name="request_key"]').evaluate(
            "(element, value) => { element.value = value; }", partial_key
        )
        self.page.once("dialog", lambda dialog: dialog.accept())
        form.locator('button[type="submit"]').click()
        expect(self.page.locator(".flash-success")).to_contain_text("Đã ghi nhận hoàn tiền")
        partial = self._refund_snapshot(invoice_id, products)
        self.assertEqual(partial["status"], "paid")
        self.assertEqual(partial["refund_count"], 1)
        self.assertEqual(partial["refund_total"], Decimal("100000.0000"))
        self.assertEqual(partial["refunded_quantity"], 1)
        self.assertEqual(partial["stocks"][products[0][0]], 4)
        self.assertEqual(partial["movement_quantity"], 1)
        partial_image = ARTIFACT_DIR / "refund-after-partial.png"
        self.page.screenshot(path=str(partial_image), full_page=True, animations="disabled")
        partial_image.chmod(0o600)

        quantity_a = self.page.locator(f'input[name="quantity_{item_a}"]')
        quantity_a.fill("1")
        self.page.locator('input[name="request_key"]').evaluate(
            "(element, value) => { element.value = value; }", partial_key
        )
        self.page.once("dialog", lambda dialog: dialog.accept())
        form = self.page.locator(".refund-form")
        form.locator('button[type="submit"]').click()
        expect(self.page.locator(".flash-info")).to_contain_text("không tạo khoản hoàn trùng")
        self.assertEqual(self._refund_snapshot(invoice_id, products), partial)

        quantity_b = self.page.locator(f'input[name="quantity_{item_b}"]')
        quantity_b.fill("2")
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.locator(".refund-form").locator('button[type="submit"]').click()
        expect(self.page.locator(".refund-history-panel")).to_be_visible()
        full_line = self._refund_snapshot(invoice_id, products)
        self.assertEqual(full_line["refund_count"], 2)
        self.assertEqual(full_line["refunded_quantity"], 3)
        self.assertEqual(full_line["stocks"][products[1][0]], 4)
        self.assertEqual(full_line["movement_quantity"], 3)

        quantity_a = self.page.locator(f'input[name="quantity_{item_a}"]')
        quantity_a.fill("1")
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.locator(".refund-form").locator('button[type="submit"]').click()
        expect(self.page.get_by_text("Tất cả số lượng trên hóa đơn đã được hoàn.")).to_be_visible()
        final = self._refund_snapshot(invoice_id, products)
        self.assertEqual(final["status"], "paid")
        self.assertEqual(final["refund_count"], 3)
        self.assertEqual(final["refund_total"], Decimal("400000.0000"))
        self.assertEqual(final["refunded_quantity"], 4)
        self.assertEqual(final["movement_count"], 3)
        self.assertEqual(final["movement_quantity"], 4)
        self.assertEqual(final["stocks"][products[0][0]], 5)
        self.assertEqual(final["stocks"][products[1][0]], 4)
        full_image = ARTIFACT_DIR / "refund-after-full.png"
        self.page.screenshot(path=str(full_image), full_page=True, animations="disabled")
        full_image.chmod(0o600)
        self._assert_browser_diagnostics()


if __name__ == "__main__":
    unittest.main(verbosity=2)

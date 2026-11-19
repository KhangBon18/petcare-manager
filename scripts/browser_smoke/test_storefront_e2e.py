"""Full Chromium Playwright E2E journey & responsive a11y suite for Customer Storefront MVP 1.0."""

from __future__ import annotations

import http.client
import os
from pathlib import Path
import re
import socket
import subprocess  # nosec B404
import sys
import tempfile
import time
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.sync_api import expect, sync_playwright
from werkzeug.datastructures import FileStorage

from petcare import create_app
from petcare.config import Config
from petcare.database.connection import get_connection
from petcare.database.initialize import initialize_database
from petcare.database.seed import seed_database
from petcare.repositories.base import fetch_one
from petcare.services import pet_service
from scripts.demo.test_accounts import DEMO_STAFF_PASSWORD


REAL_PACK_DIR = ROOT / "tests" / "fixtures" / "vision_ai4" / "real_pack"
AXE_CORE_JS = ROOT / "tests" / "a11y" / "node_modules" / "axe-core" / "axe.min.js"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class StorefrontBrowserE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_db = os.getenv("PETCARE_TEST_DB_NAME", "")
        if not re.fullmatch(r"[A-Za-z0-9_]+_test", test_db) or Config.DB_NAME != test_db:
            raise RuntimeError(
                "Storefront E2E requires DB_NAME=PETCARE_TEST_DB_NAME on an isolated _test schema."
            )
        if not os.getenv("PET_IMAGE_DIR"):
            raise RuntimeError("Storefront E2E requires isolated PET_IMAGE_DIR storage.")
        pet_image_dir = Path(os.environ["PET_IMAGE_DIR"]).resolve()
        if pet_image_dir.is_relative_to(ROOT):
            raise RuntimeError("Storefront E2E refuses pet-image storage inside the repository.")
        pet_image_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        cls.screenshot_dir = Path(
            os.environ.get(
                "STOREFRONT_DOC_SCREENSHOTS_DIR",
                str(Path(tempfile.gettempdir()) / "petcare-storefront-screenshots"),
            )
        ).resolve()
        cls.screenshot_dir.mkdir(parents=True, exist_ok=True)

        initialize_database()
        seed_database()

        # Seed a verified orange cat photo so public AI-4.0 image search returns a real match
        app = create_app({
            "TESTING": True,
            "SECRET_KEY": os.environ.get("SECRET_KEY", "storefront-e2e-secret"),
            "PET_IMAGE_DIR": Config.PET_IMAGE_DIR,
            "PRODUCT_IMAGE_DIR": Config.PRODUCT_IMAGE_DIR,
        })
        orange_path = REAL_PACK_DIR / "real-cat-orange-hold-01.jpg"
        with app.app_context(), get_connection() as conn, orange_path.open("rb") as orange_stream:
            main_tenant_id = int(fetch_one(conn, "SELECT id FROM tenants WHERE slug = 'main'")["id"])
            admin_id = int(fetch_one(conn, "SELECT id FROM users WHERE username = 'admin'")["id"])
            cls.seeded_cat_name = "Cam Xoài Storefront"
            cls.seeded_cat_id = pet_service.create_pet(
                admin_id,
                {
                    "code": f"SFCAT-{uuid4().hex[:6]}",
                    "name": cls.seeded_cat_name,
                    "species": "Mèo",
                    "breed": "Mèo ta lông ngắn",
                    "coat_color": "vàng cam",
                    "sale_price": "2400000",
                },
                FileStorage(
                    stream=orange_stream,
                    filename="orange-cat.jpg",
                    content_type="image/jpeg",
                ),
                tenant_id=main_tenant_id,
            )

        cls.port = _free_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        env = os.environ.copy()
        env.update({
            "APP_ENV": "development",
            "APP_PORT": str(cls.port),
            "PUBLIC_BASE_URL": cls.base_url,
            "PUBLIC_STORE_SLUG": "main",
            "AI_LOCAL_SPECIES_GATE_ENABLED": "1",
            "AI_FOREGROUND_EMBEDDING_ENABLED": "1",
        })
        cls.server = subprocess.Popen(  # nosec B603
            [
                sys.executable,
                "-c",
                "from petcare import create_app; create_app().run(host='127.0.0.1', port=%d, debug=False, use_reloader=False)" % cls.port,
            ],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 20.0
        ready = False
        while time.time() < deadline:
            try:
                conn = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=1)
                conn.request("GET", "/healthz")
                if conn.getresponse().status == 200:
                    ready = True
                    break
            except OSError:
                time.sleep(0.25)
        if not ready:
            cls.tearDownClass()
            raise RuntimeError("Storefront test Flask server failed to become healthy.")

    @classmethod
    def tearDownClass(cls):
        proc = getattr(cls, "server", None)
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def _assert_clean_viewport(self, page, width: int, label: str):
        overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        self.assertFalse(overflow, f"Horizontal overflow detected on {label} at {width}px")
        broken_imgs = page.evaluate("""() => Array.from(document.querySelectorAll('img')).filter(img => {
            const s = getComputedStyle(img); const r = img.getBoundingClientRect();
            const hidden = s.display === 'none' || s.visibility === 'hidden' || img.hidden || (r.width === 0 && r.height === 0);
            return !hidden && (!img.complete || img.naturalWidth === 0);
        }).map(i => i.getAttribute('src'))""")
        self.assertEqual(broken_imgs, [], f"Broken images on {label} at {width}px: {broken_imgs}")
        if AXE_CORE_JS.is_file():
            page.evaluate(AXE_CORE_JS.read_text(encoding="utf-8"))
            axe = page.evaluate("""async () => {
                const res = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa']}});
                return res.violations.filter(v => v.impact === 'critical' || v.impact === 'serious')
                    .map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.length, target: v.nodes[0]?.target}));
            }""")
            self.assertEqual(axe, [], f"Axe critical/serious violations on {label} at {width}px: {axe}")

    def test_01_full_customer_journey_and_staff_order_fulfillment(self):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            cust_ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = cust_ctx.new_page()
            console_errors = []
            page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))
            page.on("console", lambda m: console_errors.append(f"console: {m.text}") if m.type == "error" else None)

            # 1. Public Homepage (/shop)
            page.goto(f"{self.base_url}/shop", wait_until="networkidle")
            expect(page.locator("h1")).to_be_visible()
            self._assert_clean_viewport(page, 1440, "shop-home")
            page.screenshot(path=str(self.screenshot_dir / "home-1440.png"), full_page=True)

            # 2. Browse & search products (/shop/products) + detail + add to cart
            page.goto(f"{self.base_url}/shop/products", wait_until="networkidle")
            self._assert_clean_viewport(page, 1440, "shop-products")
            page.screenshot(path=str(self.screenshot_dir / "products-1440.png"), full_page=True)
            page.locator(".sf-card-title a").first.click()
            page.wait_for_load_state("networkidle")
            self._assert_clean_viewport(page, 1440, "shop-product-detail")
            page.screenshot(path=str(self.screenshot_dir / "product-detail-1440.png"), full_page=True)
            page.get_by_role("button", name=re.compile("Thêm vào giỏ|Add to cart")).click()
            page.wait_for_load_state("networkidle")
            expect(page.locator("#sf-cart-count")).not_to_have_text("0")

            # 3. Ask public Shopping AI Assistant (/shop/ai-assistant)
            page.goto(f"{self.base_url}/shop/ai-assistant", wait_until="networkidle")
            page.locator("#sf-ai-question").fill("So sánh FOOD-001 và FOOD-002")
            page.locator("#sf-ai-send").click()
            expect(page.locator(".sf-msg-bot .sf-card").first).to_be_visible(timeout=8000)
            page.locator("#sf-ai-question").fill("Doanh thu tháng này bao nhiêu?")
            page.locator("#sf-ai-send").click()
            expect(page.locator(".sf-msg-bot .sf-notice").last).to_be_visible(timeout=8000)
            self._assert_clean_viewport(page, 1440, "shop-ai-assistant")
            page.screenshot(path=str(self.screenshot_dir / "ai-assistant-1440.png"), full_page=True)

            # 4. Upload orange cat image on public AI Image Search (/shop/image-search)
            page.goto(f"{self.base_url}/shop/image-search", wait_until="networkidle")
            page.locator("#sf-image-input").set_input_files(str(REAL_PACK_DIR / "real-cat-orange-hold-01.jpg"))
            page.get_by_role("button", name=re.compile("Tìm các bé|Search similar")).click()
            page.wait_for_load_state("networkidle")
            expect(page.locator(".sf-card").first).to_be_visible()
            expect(page.locator(".sf-grid")).to_contain_text(self.seeded_cat_name)
            self._assert_clean_viewport(page, 1440, "shop-image-search")
            page.screenshot(path=str(self.screenshot_dir / "image-search-1440.png"), full_page=True)

            # Open matched cat pet detail -> add eligible pet to cart!
            page.locator(".sf-card-title a").first.click()
            page.wait_for_load_state("networkidle")
            self._assert_clean_viewport(page, 1440, "shop-pet-detail")
            page.screenshot(path=str(self.screenshot_dir / "pet-detail-1440.png"), full_page=True)
            page.get_by_role("button", name=re.compile("Thêm vào giỏ|Add to cart")).click()
            page.wait_for_load_state("networkidle")

            # Browse pets catalog
            page.goto(f"{self.base_url}/shop/pets", wait_until="networkidle")
            self._assert_clean_viewport(page, 1440, "shop-pets")
            page.screenshot(path=str(self.screenshot_dir / "pets-1440.png"), full_page=True)

            # 5. Cart page (/shop/cart)
            page.goto(f"{self.base_url}/shop/cart", wait_until="networkidle")
            expect(page.locator(".sf-cart-row")).to_have_count(2)
            self._assert_clean_viewport(page, 1440, "shop-cart")
            page.screenshot(path=str(self.screenshot_dir / "cart-1440.png"), full_page=True)

            # 6. Register Customer account + verify isolation from staff pages
            cust_email = f"cust-{uuid4().hex[:6]}@example.com"
            page.goto(f"{self.base_url}/shop/register", wait_until="networkidle")
            page.fill("#reg-name", "Trần Bảo Anh")
            page.fill("#reg-email", cust_email)
            page.fill("#reg-phone", "0905123456")
            page.fill("#reg-addr", "18 Nguyễn Huệ, Q1")
            page.fill("#reg-pw", "CustomerShop#2026!")
            page.get_by_role("button", name=re.compile("Tạo tài khoản|Register")).click()
            page.wait_for_load_state("networkidle")

            # Verify customer CANNOT visit staff /orders/ or /dashboard
            page.goto(f"{self.base_url}/orders/", wait_until="domcontentloaded")
            self.assertIn("/login", page.url)

            # 7. Checkout -> create genuine pending order
            page.goto(f"{self.base_url}/shop/checkout", wait_until="networkidle")
            page.locator('input[name="fulfillment_method"][value="cod_delivery"]').check()
            self._assert_clean_viewport(page, 1440, "shop-checkout")
            page.screenshot(path=str(self.screenshot_dir / "checkout-1440.png"), full_page=True)
            page.get_by_role("button", name=re.compile("Xác nhận đặt hàng|Place pending order")).click()
            page.wait_for_load_state("networkidle")

            order_code_match = re.search(r"ORD-\d{8}-[A-F0-9]+", page.url)
            self.assertIsNotNone(order_code_match, f"Expected order detail URL, got {page.url}")
            order_code = order_code_match.group(0)
            expect(page.locator(".sf-status-pill")).to_contain_text(re.compile("Chờ xác nhận|Pending"))
            self._assert_clean_viewport(page, 1440, "shop-order-confirmation")
            page.screenshot(path=str(self.screenshot_dir / "order-confirmation-1440.png"), full_page=True)

            # 8. Customer views own account & orders
            page.goto(f"{self.base_url}/shop/account", wait_until="networkidle")
            expect(page.locator("body")).to_contain_text(order_code)
            self._assert_clean_viewport(page, 1440, "shop-account")
            page.screenshot(path=str(self.screenshot_dir / "customer-account-1440.png"), full_page=True)

            # Responsive mobile & tablet checks
            for w in (834, 390, 320):
                page.set_viewport_size({"width": w, "height": 844})
                for route_suffix, rlabel in [("/shop", "home"), ("/shop/products", "products"), ("/shop/pets", "pets"), ("/shop/cart", "cart")]:
                    page.goto(f"{self.base_url}{route_suffix}", wait_until="networkidle")
                    self._assert_clean_viewport(page, w, f"{rlabel}-{w}")
                if w == 390:
                    page.goto(f"{self.base_url}/shop", wait_until="networkidle")
                    page.screenshot(path=str(self.screenshot_dir / "home-390.png"), full_page=False)

            cust_ctx.close()

            # 9. Staff logs in, finds the new customer order, confirms & completes payment!
            staff_ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            staff_page = staff_ctx.new_page()
            staff_page.on("pageerror", lambda e: console_errors.append(f"staff pageerror: {e}"))
            staff_page.goto(f"{self.base_url}/login", wait_until="networkidle")
            staff_page.fill('input[name="username"]', "staff1")
            staff_page.fill('input[name="password"]', DEMO_STAFF_PASSWORD)
            staff_page.click('button[type="submit"]')
            staff_page.wait_for_load_state("networkidle")

            staff_page.goto(f"{self.base_url}/orders/", wait_until="networkidle")
            expect(staff_page.locator("table")).to_contain_text(order_code)
            staff_page.screenshot(path=str(self.screenshot_dir / "staff-orders-1440.png"), full_page=True)

            staff_page.locator("a", has_text=order_code).click()
            staff_page.wait_for_load_state("networkidle")
            staff_page.locator('button[name="action"][value="confirm"]').click()
            staff_page.wait_for_load_state("networkidle")
            expect(staff_page.locator("body")).to_contain_text(re.compile("Đã xác nhận|Confirmed"))

            staff_page.locator('button[name="action"][value="complete_payment"]').click()
            staff_page.wait_for_load_state("networkidle")
            expect(staff_page.locator("body")).to_contain_text(re.compile("Hoàn tất|Completed"))
            expect(staff_page.locator("body")).to_contain_text(re.compile("Xem hóa đơn #|View invoice #"))
            staff_page.screenshot(path=str(self.screenshot_dir / "staff-order-detail-1440.png"), full_page=True)

            staff_ctx.close()
            browser.close()
            self.assertEqual(console_errors, [])


"""Real-browser Chromium E2E, responsive, and axe-core accessibility suite for PetCare AI."""

from __future__ import annotations

import http.client
import os
import re
import socket
import subprocess  # nosec B404
import sys
import tempfile
import time
import unittest
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from scripts.demo.test_accounts import DEMO_ADMIN_PASSWORD, DEMO_STAFF_PASSWORD

from petcare.config import Config
from petcare.database.connection import transaction
from petcare.database.initialize import initialize_database
from petcare.database.seed import seed_database


ROOT = Path(__file__).resolve().parents[2]
AXE_CORE_JS = ROOT / "tests" / "a11y" / "node_modules" / "axe-core" / "axe.min.js"
ARTIFACT_DIR = Path(
    os.environ.get("PLAYWRIGHT_ARTIFACT_DIR")
    or (Path(tempfile.gettempdir()) / "petcare-ai-browser-artifacts")
).resolve()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class PetCareAIBrowserE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_db = os.getenv("PETCARE_TEST_DB_NAME", "")
        if not re.fullmatch(r"[A-Za-z0-9_]+_test", test_db) or Config.DB_NAME != test_db:
            raise RuntimeError(
                "PetCare AI browser E2E requires DB_NAME=PETCARE_TEST_DB_NAME on an isolated _test schema."
            )
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        ARTIFACT_DIR.chmod(0o700)
        initialize_database()
        seed_database()

        cls.app_port = _free_port()
        cls.base_url = f"http://127.0.0.1:{cls.app_port}"
        child_env = os.environ.copy()
        child_env.update({
            "APP_ENV": "test",
            "APP_PORT": str(cls.app_port),
            "PUBLIC_BASE_URL": cls.base_url,
            "COOKIE_SECURE": "0",
            "LAN_ACCESS_ENABLED": "0",
            "AI_PROVIDER_APPROVED": "0",
            "AI_API_BASE_URL": "",
            "AI_API_KEY": "",
            "AI_MODEL": "",
            "ASSISTANT_RATE_LIMIT_PER_MINUTE": "1000",
            "ASSISTANT_IP_RATE_LIMIT_PER_MINUTE": "1000",
            "MAIL_HOST": "",
            "MEDIA_STORAGE_BACKEND": "local",
            "TENANT_EXPORT_STORAGE_BACKEND": "local",
            "PRODUCT_IMAGE_DIR": os.environ.get("PRODUCT_IMAGE_DIR", str(Config.PRODUCT_IMAGE_DIR)),
            "PET_IMAGE_DIR": os.environ.get("PET_IMAGE_DIR", str(Config.PET_IMAGE_DIR)),
            "TENANT_EXPORT_DIR": os.environ.get("TENANT_EXPORT_DIR", str(ARTIFACT_DIR / "exports")),
            "PLAYWRIGHT_ARTIFACT_DIR": str(ARTIFACT_DIR),
        })
        cls.runtime_log = (ARTIFACT_DIR / "petcare-ai-runtime.log").open("ab")
        os.chmod(cls.runtime_log.name, 0o600)
        cls.server = subprocess.Popen(  # nosec B603
            [sys.executable, str(ROOT / "run.py")],
            cwd=ROOT,
            env=child_env,
            stdout=cls.runtime_log,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 35
        ready = False
        while time.monotonic() < deadline:
            if cls.server.poll() is not None:
                raise RuntimeError(f"PetCare AI Flask process exited with {cls.server.returncode}.")
            try:
                probe = http.client.HTTPConnection("127.0.0.1", cls.app_port, timeout=1)
                try:
                    probe.request("GET", "/readyz")
                    resp = probe.getresponse()
                    resp.read()
                    if resp.status == 200:
                        ready = True
                        break
                finally:
                    probe.close()
            except OSError:
                pass
            time.sleep(0.2)
        if not ready:
            raise RuntimeError("PetCare AI Flask process did not reach /readyz=200.")

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        browser = getattr(cls, "browser", None)
        if browser:
            browser.close()
        playwright = getattr(cls, "playwright", None)
        if playwright:
            playwright.stop()
        server = getattr(cls, "server", None)
        if server and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        runtime_log = getattr(cls, "runtime_log", None)
        if runtime_log:
            runtime_log.close()

    def _new_logged_in_page(
        self,
        username: str,
        password: str,
        *,
        width: int = 1366,
        height: int = 900,
        with_axe: bool = False,
    ):
        context = self.browser.new_context(viewport={"width": width, "height": height})
        if with_axe and AXE_CORE_JS.is_file():
            context.add_init_script(path=str(AXE_CORE_JS))
        page = context.new_page()
        console_errors: list[str] = []
        page.on(
            "console",
            lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
        )
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        page.goto(f"{self.base_url}/login", wait_until="domcontentloaded")
        page.fill('input[name="store_slug"]', "main")
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_url(f"{self.base_url}/dashboard")
        return context, page, console_errors

    def test_navigation_multiturn_apartment_cat_and_desktop_screenshot(self):
        context, page, console_errors = self._new_logged_in_page("admin", DEMO_ADMIN_PASSWORD)
        try:
            # Floating shortcut remains accessible on /dashboard
            expect(page.locator("#assistant-launcher")).to_be_visible()

            # Prominent sidebar link navigates to full-page /assistant/chat workspace
            nav_link = page.locator("aside.sidebar a.nav-link-assistant")
            expect(nav_link).to_be_visible()
            nav_link.click()
            page.wait_for_url(f"{self.base_url}/assistant/chat")

            # Floating widget launcher is suppressed on the dedicated full-page workspace
            expect(page.locator("#assistant-launcher")).to_be_hidden()
            expect(page.locator("#ai-workspace")).to_be_visible()

            # Turn 1: Apartment cat inquiry triggers guided clarification
            page.fill("#ai-workspace-input", "Tôi muốn nuôi mèo hợp căn hộ")
            page.click("#ai-workspace-send")
            assistant_msgs = page.locator(".ai-turn-bot:not(.is-loading)")
            expect(assistant_msgs).to_have_count(1)
            expect(assistant_msgs.nth(0)).to_contain_text("ngân sách")

            # Turn 2: Follow-up supplies calm temperament + 8M VND ceiling -> merges context & returns cards
            page.fill("#ai-workspace-input", "Hiền, dưới 8 triệu VND")
            page.click("#ai-workspace-send")
            expect(assistant_msgs).to_have_count(2)
            rec_cards = assistant_msgs.nth(1).locator(".ai-rec-card")
            expect(rec_cards.first).to_be_visible()

            # Context chips reflect merged multi-turn slots
            chips_text = page.locator("#ai-context-chips").inner_text()
            self.assertIn("Mèo", chips_text)
            self.assertIn("Căn hộ", chips_text)

            page.screenshot(
                path=str(ARTIFACT_DIR / "petcare-ai-workspace-desktop.png"),
                full_page=False,
            )
            self.assertEqual(console_errors, [])
        finally:
            context.close()

    def test_english_product_recommendations_compare_tray_and_mobile_layout(self):
        context, page, console_errors = self._new_logged_in_page("staff1", DEMO_STAFF_PASSWORD)
        try:
            # Switch UI language to English via topbar locale selector
            page.goto(f"{self.base_url}/assistant/chat", wait_until="domcontentloaded")
            with page.expect_navigation(wait_until="domcontentloaded"):
                page.select_option("#language-select", "en")

            expect(page.locator("html")).to_have_attribute("lang", "en")
            page.fill("#ai-workspace-input", "Which food should I consider for my adult cat?")
            page.click("#ai-workspace-send")

            assistant_msgs = page.locator(".ai-turn-bot:not(.is-loading)")
            expect(assistant_msgs).to_have_count(1)
            checkboxes = assistant_msgs.nth(0).locator('input[data-compare-code]')
            self.assertGreaterEqual(checkboxes.count(), 2)

            # Check first two products -> compare tray becomes visible -> submit comparison
            checkboxes.nth(0).check()
            checkboxes.nth(1).check()
            expect(page.locator("#ai-compare-tray")).to_be_visible()
            page.click("#ai-compare-submit")

            expect(assistant_msgs).to_have_count(2)
            expect(assistant_msgs.nth(1).locator(".ai-comparison-table")).to_be_visible()
            page.screenshot(
                path=str(ARTIFACT_DIR / "petcare-ai-comparison-desktop.png"),
                full_page=False,
            )

            # Resize to mobile 390x844 -> stacked mobile comparison cards become visible with zero horizontal overflow
            page.set_viewport_size({"width": 390, "height": 844})
            expect(assistant_msgs.nth(1).locator(".ai-comparison-mobile-card").first).to_be_visible()
            overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
            self.assertLessEqual(overflow, 0)
            page.screenshot(
                path=str(ARTIFACT_DIR / "petcare-ai-mobile-390.png"),
                full_page=False,
            )
            self.assertEqual(console_errors, [])
        finally:
            with transaction() as conn:
                cur = conn.cursor()
                try:
                    cur.execute("UPDATE users SET preferred_locale = 'vi' WHERE username IN ('admin', 'staff1')")
                finally:
                    cur.close()
            context.close()

    def test_shopper_preview_isolation_knowledge_citations_and_emergency_escalation(self):
        context, page, console_errors = self._new_logged_in_page("admin", DEMO_ADMIN_PASSWORD)
        try:
            page.goto(f"{self.base_url}/assistant/chat", wait_until="domcontentloaded")

            # Toggle to Shopper Preview (QA)
            shopper_btn = page.locator('[data-scope-value="shopper_preview"]')
            shopper_btn.click()
            expect(shopper_btn).to_have_attribute("aria-pressed", "true")
            expect(page.locator('#ai-workspace-messages [data-workspace-only="true"]').first).to_be_hidden()

            # 1. Knowledge base retrieval with source citation & non-vet disclaimer
            page.fill("#ai-workspace-input", "Cách chuẩn bị căn hộ và khay vệ sinh khi mới đón mèo?")
            page.click("#ai-workspace-send")
            assistant_msgs = page.locator(".ai-turn-bot:not(.is-loading)")
            expect(assistant_msgs).to_have_count(1)
            expect(assistant_msgs.nth(0).locator(".ai-citation-card").first).to_be_visible()
            expect(assistant_msgs.nth(0).locator(".ai-safety-banner")).to_be_visible()

            # 2. Urgent veterinary emergency escalation
            page.fill("#ai-workspace-input", "Mèo nhà mình nhai lá hoa ly và đang khó thở!")
            page.click("#ai-workspace-send")
            expect(assistant_msgs).to_have_count(2)
            expect(assistant_msgs.nth(1).locator(".ai-safety-banner--emergency")).to_be_visible()

            # 3. Internal store KPI query is blocked in Shopper Preview even for an admin user
            page.fill("#ai-workspace-input", "Sản phẩm nào bán chạy nhất tuần này?")
            page.click("#ai-workspace-send")
            expect(assistant_msgs).to_have_count(3)
            self.assertEqual(assistant_msgs.nth(2).locator(".ai-ops-insight").count(), 0)
            self.assertEqual(console_errors, [])
        finally:
            context.close()

    def test_responsive_viewports_and_axe_core_zero_serious_or_critical_violations(self):
        context, page, console_errors = self._new_logged_in_page(
            "admin", DEMO_ADMIN_PASSWORD, with_axe=True
        )
        try:
            page.goto(f"{self.base_url}/assistant/chat", wait_until="domcontentloaded")
            for width in (320, 390, 768, 1024, 1440):
                height = 740 if width < 768 else 900
                page.set_viewport_size({"width": width, "height": height})
                overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
                self.assertLessEqual(
                    overflow,
                    0,
                    f"Horizontal overflow ({overflow}px) detected on /assistant/chat at {width}px",
                )

            if AXE_CORE_JS.is_file():
                page.set_viewport_size({"width": 1280, "height": 900})
                page.evaluate(
                    "document.getAnimations().forEach(animation => { try { animation.finish(); } catch (_) {} })"
                )
                axe_results = page.evaluate("""async () => await window.axe.run(document.querySelector('#main-content'), {
                    runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']}
                })""")
                serious_or_critical = [
                    {
                        "id": v.get("id"),
                        "impact": v.get("impact"),
                        "nodes": len(v.get("nodes", [])),
                    }
                    for v in axe_results.get("violations", [])
                    if v.get("impact") in {"serious", "critical"}
                ]
                self.assertEqual(serious_or_critical, [])
            self.assertEqual(console_errors, [])
        finally:
            context.close()

    def test_ai_2_1_vet_triage_multiturn_correction_multi_intent_and_floating_widget(self):
        # Part A: Existing floating widget + keyboard Enter/Escape + Vietnamese multi-intent & slot-removal corrections
        context, page, console_errors = self._new_logged_in_page(
            "admin", DEMO_ADMIN_PASSWORD, width=1440, height=900
        )
        try:
            # 1. Floating widget on /dashboard: open, keyboard submit colloquial query, Escape to close
            expect(page.locator("#assistant-launcher")).to_be_visible()
            page.click("#assistant-launcher")
            expect(page.locator("#assistant-panel")).to_be_visible()
            expect(page.locator("#assistant-input")).to_be_focused()

            page.fill("#assistant-input", "rcm hạt cho mèo trưởng thành 4 xị quay đầu")
            page.press("#assistant-input", "Enter")
            expect(page.locator('#assistant-form[aria-busy="false"]')).to_be_visible()
            expect(page.locator("#assistant-messages .assistant-result-card").first).to_be_visible()

            page.keyboard.press("Escape")
            expect(page.locator("#assistant-panel")).to_be_hidden()
            expect(page.locator("#assistant-launcher")).to_have_attribute("aria-expanded", "false")

            # 2. Full-page /assistant/chat: bounded multi-intent (cited KB + product cards in one turn)
            page.goto(f"{self.base_url}/assistant/chat", wait_until="domcontentloaded")
            page.fill(
                "#ai-workspace-input",
                "Cách chuyển đổi thức ăn mới cho mèo trong 7-10 ngày như thế nào và gợi ý hạt mèo trưởng thành dưới 400k?",
            )
            page.press("#ai-workspace-input", "Enter")
            assistant_msgs = page.locator(".ai-turn-bot:not(.is-loading)")
            expect(assistant_msgs).to_have_count(1)
            expect(assistant_msgs.nth(0).locator(".ai-citation-card").first).to_be_visible()
            expect(assistant_msgs.nth(0).locator(".ai-rec-card").first).to_be_visible()
            assistant_msgs.nth(0).locator(".ai-rec-card").first.scroll_into_view_if_needed()
            page.screenshot(
                path=str(ARTIFACT_DIR / "petcare-ai-2-1-multi-intent-desktop.png"),
                full_page=False,
            )

            # 3. Reset & verify multi-turn slot-removal correction (remove chicken allergy + clear price ceiling)
            page.click("#ai-workspace-reset")
            expect(page.locator("#ai-welcome-panel")).to_be_visible()

            page.fill("#ai-workspace-input", "Gợi ý hạt cho mèo trưởng thành dị ứng gà dưới 200k")
            page.press("#ai-workspace-input", "Enter")
            expect(assistant_msgs).to_have_count(1)
            expect(page.locator('#ai-context-chips [data-slot="allergies"]')).to_contain_text("chicken")
            expect(page.locator('#ai-context-chips [data-slot="budget"]')).to_contain_text("200.000")

            page.fill(
                "#ai-workspace-input",
                "À nhầm, bé không dị ứng gà đâu và thôi bỏ giới hạn giá đi",
            )
            page.press("#ai-workspace-input", "Enter")
            expect(assistant_msgs).to_have_count(2)
            expect(page.locator('#ai-context-chips [data-slot="species"]')).to_contain_text("Mèo")
            expect(page.locator('#ai-context-chips [data-slot="life_stage"]')).to_contain_text("Trưởng thành")
            expect(page.locator('#ai-context-chips [data-slot="allergies"]')).to_have_count(0)
            expect(page.locator('#ai-context-chips [data-slot="budget"]')).to_have_count(0)
            expect(assistant_msgs.nth(1).locator(".ai-rec-card").first).to_be_visible()
            self.assertEqual(console_errors, [])
        finally:
            context.close()

        # Part B: English descriptive veterinary triage (Desktop + Mobile) & staff permission boundaries
        staff_ctx, staff_page, staff_errors = self._new_logged_in_page(
            "staff1", DEMO_STAFF_PASSWORD, width=1440, height=900
        )
        try:
            staff_page.goto(f"{self.base_url}/assistant/chat", wait_until="domcontentloaded")
            with staff_page.expect_navigation(wait_until="domcontentloaded"):
                staff_page.select_option("#language-select", "en")
            expect(staff_page.locator("html")).to_have_attribute("lang", "en")

            # 1. Descriptive urinary obstruction in English must render emergency alert + KB citation, NEVER cat litter cards
            staff_page.fill(
                "#ai-workspace-input",
                "My male cat keeps straining in the litter box but has produced no urine since last night.",
            )
            staff_page.press("#ai-workspace-input", "Enter")
            bot_turns = staff_page.locator(".ai-turn-bot:not(.is-loading)")
            expect(bot_turns).to_have_count(1)
            expect(bot_turns.nth(0).locator(".ai-safety-banner--emergency")).to_be_visible()
            expect(bot_turns.nth(0).locator(".ai-citation-card").first).to_be_visible()
            self.assertEqual(bot_turns.nth(0).locator(".ai-rec-card").count(), 0)
            bot_turns.nth(0).locator(".ai-safety-banner--emergency").scroll_into_view_if_needed()
            staff_page.screenshot(
                path=str(ARTIFACT_DIR / "petcare-ai-2-1-vet-triage-desktop.png"),
                full_page=False,
            )

            # Mobile 390x844 responsive check on emergency banner + citation cards
            staff_page.set_viewport_size({"width": 390, "height": 844})
            expect(bot_turns.nth(0).locator(".ai-safety-banner--emergency")).to_be_visible()
            bot_turns.nth(0).locator(".ai-safety-banner--emergency").scroll_into_view_if_needed()
            mobile_overflow = staff_page.evaluate(
                "() => document.documentElement.scrollWidth - window.innerWidth"
            )
            self.assertLessEqual(mobile_overflow, 0)
            staff_page.screenshot(
                path=str(ARTIFACT_DIR / "petcare-ai-2-1-vet-triage-mobile-390.png"),
                full_page=False,
            )

            # 2. Staff permission boundary on multi-operational query (sales allowed, 8-week inventory forecast admin-restricted)
            staff_page.set_viewport_size({"width": 1440, "height": 900})
            staff_page.fill(
                "#ai-workspace-input",
                "Show top-selling products this week and inventory forecast",
            )
            staff_page.press("#ai-workspace-input", "Enter")
            expect(bot_turns).to_have_count(2)
            expect(bot_turns.nth(1).locator(".ai-ops-insight").first).to_be_visible()
            expect(bot_turns.nth(1)).to_contain_text("admin")
            self.assertEqual(staff_errors, [])
        finally:
            with transaction() as conn:
                cur = conn.cursor()
                try:
                    cur.execute("UPDATE users SET preferred_locale = 'vi' WHERE username IN ('admin', 'staff1')")
                finally:
                    cur.close()
            staff_ctx.close()

    def test_ai_2_2_head_pressing_triage_missing_data_and_budget_replacement(self):
        context, page, console_errors = self._new_logged_in_page(
            "admin", DEMO_ADMIN_PASSWORD, width=1440, height=900
        )
        try:
            page.goto(f"{self.base_url}/assistant/chat", wait_until="domcontentloaded")
            bot_turns = page.locator(".ai-turn-bot:not(.is-loading)")

            # 1. Newly closed head-pressing + scleral icterus emergency -> emergency banner + citation, 0 pet cards
            page.fill(
                "#ai-workspace-input",
                "My senior cat has been standing in the corner pressing her forehead flat against the wall for an hour and the whites of her eyes turned bright yellow.",
            )
            page.press("#ai-workspace-input", "Enter")
            expect(bot_turns).to_have_count(1)
            expect(bot_turns.nth(0).locator(".ai-safety-banner--emergency")).to_be_visible()
            expect(bot_turns.nth(0).locator(".ai-citation-card").first).to_be_visible()
            self.assertEqual(bot_turns.nth(0).locator(".ai-rec-card").count(), 0)

            # 2. Undocumented feed-label nutrient % / taurine mg -> explicit .ai-missing-note without false medical boundary
            page.fill(
                "#ai-workspace-input",
                "Túi hạt FOOD-004 có chính xác bao nhiêu phần trăm chất béo thô và bao nhiêu mg taurine?",
            )
            page.press("#ai-workspace-input", "Enter")
            expect(bot_turns).to_have_count(2)
            expect(bot_turns.nth(1).locator(".ai-missing-note")).to_be_visible()
            self.assertEqual(bot_turns.nth(1).locator(".ai-safety-banner").count(), 0)
            bot_turns.nth(1).locator(".ai-missing-note").scroll_into_view_if_needed()
            page.screenshot(
                path=str(ARTIFACT_DIR / "petcare-ai-2-2-safety-and-missing-data-desktop.png"),
                full_page=False,
            )

            # 3. Simultaneous old budget cap removal + replacement in a single follow-up turn
            page.click("#ai-workspace-reset")
            expect(page.locator("#ai-welcome-panel")).to_be_visible()

            page.fill("#ai-workspace-input", "Gợi ý mèo hiền hợp căn hộ dưới 5 triệu VND")
            page.press("#ai-workspace-input", "Enter")
            expect(bot_turns).to_have_count(1)
            expect(page.locator('#ai-context-chips [data-slot="budget"]')).to_contain_text("5.000.000")

            page.fill(
                "#ai-workspace-input",
                "Thôi bỏ mức trần 5 triệu cũ đi, nâng lên dưới 7 triệu rưỡi nhé",
            )
            page.press("#ai-workspace-input", "Enter")
            expect(bot_turns).to_have_count(2)
            expect(page.locator('#ai-context-chips [data-slot="budget"]')).to_contain_text("7.500.000")
            self.assertEqual(console_errors, [])
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main()

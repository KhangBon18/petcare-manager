"""Real Chromium E2E verification for AI-4.0b /pets/find-similar (all 14 browser acceptance criteria)."""

from __future__ import annotations

import http.client
import io
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess  # nosec B404
import sys
import tempfile
import time
import unittest
from urllib.parse import urlsplit
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright
from werkzeug.datastructures import FileStorage

from petcare import create_app
from petcare.config import Config
from petcare.database.connection import get_connection
from petcare.database.create_store import create_store
from petcare.database.initialize import initialize_database
from petcare.database.seed import seed_database
from petcare.repositories.base import fetch_one
from petcare.services import pet_service
from scripts.demo.test_accounts import DEMO_ADMIN_PASSWORD, DEMO_STAFF_PASSWORD

ROOT = Path(__file__).resolve().parents[2]
DEMO_PETS_DIR = ROOT / "assets" / "demo" / "pets"
REAL_PACK_DIR = ROOT / "tests" / "fixtures" / "vision_ai4" / "real_pack"
AXE_CORE_JS = ROOT / "tests" / "a11y" / "node_modules" / "axe-core" / "axe.min.js"
ARTIFACT_DIR = Path(
    os.environ.get(
        "PLAYWRIGHT_ARTIFACT_DIR",
        str(Path(tempfile.gettempdir()) / "petcare-ai40b-browser-artifacts"),
    )
).resolve()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _path_only(url: str) -> str:
    return urlsplit(url).path


class AI4ImageMatchingBrowserE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_db = os.getenv("PETCARE_TEST_DB_NAME", "")
        if not re.fullmatch(r"[A-Za-z0-9_]+_test", test_db) or Config.DB_NAME != test_db:
            raise RuntimeError(
                "AI-4.0b browser E2E requires DB_NAME=PETCARE_TEST_DB_NAME on an isolated _test schema."
            )
        if not os.getenv("PET_IMAGE_DIR"):
            raise RuntimeError("AI-4.0b browser E2E requires isolated PET_IMAGE_DIR storage.")
        pet_image_dir = Path(os.environ["PET_IMAGE_DIR"]).resolve()
        if pet_image_dir.is_relative_to(ROOT):
            raise RuntimeError("AI-4.0b browser E2E refuses pet-image storage inside the repository.")

        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        ARTIFACT_DIR.chmod(0o700)
        pet_image_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        initialize_database()
        seed_database()

        with get_connection() as conn:
            cls.main_tenant_id = fetch_one(conn, "SELECT id FROM tenants WHERE slug = 'main'")["id"]
            cls.main_pet157_photo = fetch_one(
                conn,
                "SELECT photo_filename FROM pets WHERE tenant_id = %s AND code = 'PET-157'",
                (cls.main_tenant_id,),
            )["photo_filename"]

        # Secondary store where demo-cat-25.png and real_pack photos are genuinely absent
        suffix = uuid4().hex[:8]
        cls.branch_slug = f"ai4-e2e-{suffix}"
        cls.branch_user = f"ai4e2e_{suffix}"
        cls.branch_pw = secrets.token_urlsafe(24)
        cls.branch_tenant_id, cls.branch_user_id = create_store(
            cls.branch_slug,
            "PetCare AI4 E2E Store",
            cls.branch_user,
            "AI4 E2E Owner",
            cls.branch_pw,
        )

        setup_app = create_app({
            "TESTING": True,
            "SECRET_KEY": secrets.token_urlsafe(32),
            "PET_IMAGE_DIR": pet_image_dir,
            "AI_VISION_ENABLED": False,
            "AI_PROVIDER_APPROVED": False,
        })
        branch_seed = (
            ("E2E-CAT-01", "Gừng Nhánh", "Mèo", "British Shorthair", "cam vằn", "vàng đồng", "mèo mướp cam", "demo-cat-03.png"),
            ("E2E-CAT-02", "Mật Nhánh", "Mèo", "Scottish Fold", "vàng kem", "vàng đồng", "tai cụp lông cam kem", "demo-cat-10.png"),
            ("E2E-CAT-03", "Đêm Nhánh", "Mèo", "Bombay", "đen tuyền", "vàng đồng", "lông đen bóng", "demo-cat-16.png"),
            ("E2E-CAT-04", "Khói Nhánh", "Mèo", "British Shorthair", "xám xanh", "vàng hổ phách", "lông ngắn dày", "demo-cat-01.png"),
            ("E2E-DOG-01", "Bắp Nhánh", "Chó", "Golden Retriever", "vàng kim", "nâu ấm", "lông dài vàng, dáng lớn", "demo-dog-01.png"),
            ("E2E-DOG-02", "Cam Nhánh", "Chó", "Pomeranian", "cam vàng", "nâu đậm", "lông xù dày, dáng nhỏ", "demo-dog-21.png"),
        )
        with setup_app.app_context():
            for code, name, species, breed, coat, eyes, tags, asset in branch_seed:
                raw = (DEMO_PETS_DIR / asset).read_bytes()
                pet_service.create_pet(
                    cls.branch_user_id,
                    {
                        "code": code,
                        "name": name,
                        "species": species,
                        "breed": breed,
                        "sex": "female",
                        "coat_color": coat,
                        "eye_color": eyes,
                        "appearance_tags": tags,
                        "sale_price": "3600000",
                    },
                    image_upload=FileStorage(stream=io.BytesIO(raw), filename=asset, content_type="image/png"),
                    tenant_id=cls.branch_tenant_id,
                )

        cls.app_port = _free_port()
        cls.base_url = f"http://127.0.0.1:{cls.app_port}"
        child_env = os.environ.copy()
        child_env.update({
            "APP_ENV": "test",
            "APP_PORT": str(cls.app_port),
            "PUBLIC_BASE_URL": cls.base_url,
            "COOKIE_SECURE": "0",
            "LAN_ACCESS_ENABLED": "0",
            "AI_VISION_ENABLED": "0",
            "AI_LOCAL_SPECIES_GATE_ENABLED": "1",
            "AI_PROVIDER_APPROVED": "0",
            "AI_API_BASE_URL": "",
            "AI_API_KEY": "",
            "AI_MODEL": "",
            "VISION_RATE_LIMIT_PER_MINUTE": "1000",
            "VISION_IP_RATE_LIMIT_PER_MINUTE": "1000",
            "MAIL_HOST": "",
            "MEDIA_STORAGE_BACKEND": "local",
            "TENANT_EXPORT_STORAGE_BACKEND": "local",
            "PET_IMAGE_DIR": str(pet_image_dir),
            "PRODUCT_IMAGE_DIR": str(ARTIFACT_DIR / "ai4-products"),
            "TENANT_EXPORT_DIR": str(ARTIFACT_DIR / "ai4-exports"),
        })
        cls.runtime_log = (ARTIFACT_DIR / "ai4b-matching-runtime.log").open("ab")
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
                raise RuntimeError(f"AI-4.0b Flask server exited early ({cls.server.returncode}).")
            try:
                probe = http.client.HTTPConnection("127.0.0.1", cls.app_port, timeout=1)
                try:
                    probe.request("GET", "/readyz")
                    if probe.getresponse().status == 200:
                        ready = True
                        break
                finally:
                    probe.close()
            except OSError:
                pass
            time.sleep(0.2)
        if not ready:
            raise RuntimeError("AI-4.0b Flask server did not reach /readyz=200.")

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        browser = getattr(cls, "browser", None)
        if browser:
            browser.close()
        pw = getattr(cls, "playwright", None)
        if pw:
            pw.stop()
        server = getattr(cls, "server", None)
        if server and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        rlog = getattr(cls, "runtime_log", None)
        if rlog:
            rlog.close()

    def setUp(self):
        self.context = self.browser.new_context(
            viewport={"width": 1440, "height": 960},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )
        self.page = self.context.new_page()
        self.page.set_default_timeout(12_000)
        self.page_errors: list[str] = []
        self.failed_requests: list[str] = []
        self.server_500s: list[tuple[int, str]] = []
        self.page.on("pageerror", lambda err: self.page_errors.append(str(err)))
        self.page.on("requestfailed", lambda req: self.failed_requests.append(_path_only(req.url)))
        self.page.on(
            "response",
            lambda resp: self.server_500s.append((resp.status, _path_only(resp.url)))
            if resp.status >= 500
            else None,
        )

    def tearDown(self):
        stem = re.sub(r"[^A-Za-z0-9_-]+", "_", self.id().split(".")[-1]).strip("_")
        if self.page and not self.page.is_closed():
            shot = ARTIFACT_DIR / f"ai40b-{stem}.png"
            self.page.screenshot(path=str(shot), full_page=True, animations="disabled")
            shot.chmod(0o600)
        self.context.close()
        self.assertEqual(self.page_errors, [])
        self.assertEqual(self.failed_requests, [])
        self.assertEqual(self.server_500s, [])

    def _login(self, store_slug: str, username: str, password: str):
        self.page.goto(f"{self.base_url}/login", wait_until="domcontentloaded")
        self.page.locator('input[name="store_slug"]').fill(store_slug)
        self.page.locator('input[name="username"]').fill(username)
        self.page.locator('input[name="password"]').fill(password)
        self.page.locator('.login-card form button[type="submit"]').click()
        self.page.wait_for_url(f"{self.base_url}/dashboard")

    def _submit_image_search(self, image_path: Path, species: str = "", status: str = "available"):
        self.page.goto(f"{self.base_url}/pets/find-similar", wait_until="domcontentloaded")
        self.page.locator('input[name="species"]').fill(species)
        self.page.locator('select[name="status"]').select_option(status)
        self.page.locator("#pet-search-photo").set_input_files(str(image_path))
        self.page.locator('.visual-search-form button[type="submit"]').click()
        expect(self.page.locator("section.visual-results")).to_be_visible()

    def _assert_axe_clean(self, label: str):
        self.assertTrue(AXE_CORE_JS.is_file(), "axe-core must be installed in tests/a11y.")
        self.assertTrue(self.page.evaluate("typeof axe === 'object'"), "axe-core must load via add_init_script.")
        self.page.evaluate(
            "document.getAnimations().forEach(a => { try { a.finish(); } catch (_) {} })"
        )
        violations = self.page.evaluate(
            """async () => {
              const res = await axe.run(document.querySelector('#main-content'), {
                runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']}
              });
              return res.violations
                .filter(v => v.impact === 'critical' || v.impact === 'serious')
                .map(v => ({id: v.id, impact: v.impact, help: v.help}));
            }"""
        )
        self.assertEqual(violations, [], f"Axe violations in {label}: {violations}")

    # Scenarios 1 & 2: Stored cat & stored dog -> exact match #1, zero cross-species
    def test_01_stored_cat_and_dog_exact_matches_rank_first(self):
        self._login("main", "admin", DEMO_ADMIN_PASSWORD)
        self._submit_image_search(DEMO_PETS_DIR / "miu-orange-cream.png")
        cards = self.page.locator(".visual-results-grid .pet-card")
        self.assertGreaterEqual(cards.count(), 1)
        self.assertEqual(cards.first.get_attribute("data-pet-code"), "PET-001")
        self.assertEqual(cards.first.get_attribute("data-match-tier"), "exact_image_match")
        expect(cards.first.locator(".match-score-label")).to_contain_text("100/100")
        for idx in range(cards.count()):
            self.assertEqual(cards.nth(idx).get_attribute("data-pet-species"), "Mèo")

        self._submit_image_search(DEMO_PETS_DIR / "demo-dog-11.png")
        dog_cards = self.page.locator(".visual-results-grid .pet-card")
        self.assertGreaterEqual(dog_cards.count(), 1)
        self.assertEqual(dog_cards.first.get_attribute("data-pet-code"), "PET-111")
        self.assertEqual(dog_cards.first.get_attribute("data-match-tier"), "exact_image_match")
        for idx in range(dog_cards.count()):
            self.assertEqual(dog_cards.nth(idx).get_attribute("data-pet-species"), "Chó")

    # Scenarios 3, 5 & 11: NEW orange cat photo -> auto-detected as cat without manual filter,
    # zero golden dogs, zero false identity claims, accessible WCAG AA cards
    def test_02_new_real_orange_cat_auto_detected_without_manual_filter(self):
        self.page.add_init_script(path=str(AXE_CORE_JS))
        self._login(self.branch_slug, self.branch_user, self.branch_pw)
        self._submit_image_search(REAL_PACK_DIR / "real-cat-orange-hold-01.jpg", species="")
        panel = self.page.locator("section.visual-results")
        self.assertEqual(panel.get_attribute("data-verified-species"), "cat")
        self.assertEqual(panel.get_attribute("data-verified-species-source"), "local_detector")
        self.assertEqual(panel.get_attribute("data-subject-status"), "one_cat")
        expect(self.page.locator("[data-recognized-species-banner]")).to_contain_text("Mèo")
        expect(self.page.locator("[data-recognized-species-banner]")).to_contain_text("tự động")

        cards = self.page.locator(".visual-results-grid .pet-card")
        self.assertGreaterEqual(cards.count(), 1)
        # CASE 3 (AI-4.0c): Shorthair ginger tabby ranks E2E-CAT-01 (ginger tabby) #1 ahead of solid cream Scottish Fold!
        self.assertEqual(cards.first.get_attribute("data-pet-code"), "E2E-CAT-01")
        expect(cards.first.locator(".match-reasons")).to_contain_text("Hình thái")
        returned_codes = set()
        for idx in range(cards.count()):
            card = cards.nth(idx)
            self.assertEqual(card.get_attribute("data-pet-species"), "Mèo")
            self.assertEqual(card.get_attribute("data-match-tier"), "visually_similar_candidate")
            expect(card.locator(".identity-caution-note")).to_be_visible()
            returned_codes.add(card.get_attribute("data-pet-code"))
        self.assertTrue(returned_codes.issubset({"E2E-CAT-01", "E2E-CAT-02"}))
        self._assert_axe_clean("auto_detected_orange_cat")

    # Scenarios 4 & 6 + Contradiction Guard: NEW dog photo -> auto-detected as dog without manual filter,
    # zero cats, and manual 'Mèo' override is rejected as species_contradiction
    def test_03_new_real_dog_auto_detected_and_blocks_contradictory_cat_override(self):
        self._login(self.branch_slug, self.branch_user, self.branch_pw)
        dog_photo = REAL_PACK_DIR / "real-dog-golden-cal-01.jpg"
        self._submit_image_search(dog_photo, species="")
        panel = self.page.locator("section.visual-results")
        self.assertEqual(panel.get_attribute("data-verified-species"), "dog")
        self.assertEqual(panel.get_attribute("data-verified-species-source"), "local_detector")
        expect(self.page.locator("[data-recognized-species-banner]")).to_contain_text("Chó")
        cards = self.page.locator(".visual-results-grid .pet-card")
        self.assertGreaterEqual(cards.count(), 1)
        # CASE 4 (AI-4.0c): Real Golden Retriever ranks Golden Retriever (E2E-DOG-01) #1 ahead of tiny Pomeranian (E2E-DOG-02)!
        self.assertEqual(cards.first.get_attribute("data-pet-code"), "E2E-DOG-01")
        for idx in range(cards.count()):
            self.assertEqual(cards.nth(idx).get_attribute("data-pet-species"), "Chó")
            self.assertEqual(cards.nth(idx).get_attribute("data-match-tier"), "visually_similar_candidate")

        # Never let manual species='Mèo' turn a dog photo into a cat match!
        self._submit_image_search(dog_photo, species="Mèo")
        self.assertEqual(self.page.locator(".visual-results-grid .pet-card").count(), 0)
        self.assertEqual(
            self.page.locator("[data-empty-match-state]").get_attribute("data-reason"),
            "species_contradiction",
        )

    # Scenarios 7 & 8: Invoice screenshot AND natural non-animal / plush toy photographs -> rejected
    def test_04_invoice_and_natural_non_animal_photos_rejected(self):
        self._login(self.branch_slug, self.branch_user, self.branch_pw)
        for img_path, expected_reasons in (
            (ROOT / "docs" / "assets" / "phase62" / "classroom-invoice.png", {"non_photographic_or_low_texture"}),
            (REAL_PACK_DIR / "real-neg-sofa-cal-03.jpg", {"no_animal_detected"}),
            (REAL_PACK_DIR / "real-neg-blanket-hold-02.jpg", {"no_animal_detected"}),
            (REAL_PACK_DIR / "real-neg-toy-cal-01.jpg", {"stuffed_toy_or_figurine"}),
        ):
            self._submit_image_search(img_path, species="")
            self.assertEqual(self.page.locator(".visual-results-grid .pet-card").count(), 0)
            empty = self.page.locator("[data-empty-match-state]")
            expect(empty).to_be_visible()
            self.assertIn(empty.get_attribute("data-reason"), expected_reasons)

    # Scenarios 9 & 10: Multiple animals AND low-confidence ambiguous image -> reject / abstain
    def test_05_multi_animal_and_low_confidence_photos_abstain(self):
        self._login(self.branch_slug, self.branch_user, self.branch_pw)
        self._submit_image_search(REAL_PACK_DIR / "real-multi-catdog-hold-01.jpg", species="")
        self.assertEqual(self.page.locator(".visual-results-grid .pet-card").count(), 0)
        empty_multi = self.page.locator("[data-empty-match-state]")
        self.assertEqual(empty_multi.get_attribute("data-reason"), "multiple_animals_detected")
        expect(empty_multi).to_contain_text("2 động vật")

        self._submit_image_search(REAL_PACK_DIR / "real-cat-other-cal-04.jpg", species="")
        self.assertEqual(self.page.locator(".visual-results-grid .pet-card").count(), 0)
        empty_amb = self.page.locator("[data-empty-match-state]")
        self.assertEqual(empty_amb.get_attribute("data-reason"), "ambiguous_subject")

    # Scenarios 12 & 14: Empty result state (verified cat, 0 matching inactive records), accessibility & mobile 390px
    def test_06_empty_result_state_accessibility_and_mobile_viewport(self):
        self.page.add_init_script(path=str(AXE_CORE_JS))
        self._login(self.branch_slug, self.branch_user, self.branch_pw)
        self._submit_image_search(REAL_PACK_DIR / "real-cat-orange-hold-01.jpg", species="", status="inactive")
        panel = self.page.locator("section.visual-results")
        self.assertEqual(panel.get_attribute("data-verified-species"), "cat")
        empty = self.page.locator("[data-empty-match-state]")
        expect(empty).to_be_visible()
        self.assertEqual(empty.get_attribute("data-reason"), "below_similarity_threshold")
        self._assert_axe_clean("empty_verified_species_state")
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), 390)

    # Scenario 13: Tenant isolation and staff RBAC permissions
    def test_07_tenant_isolation_and_staff_permissions(self):
        self._login(self.branch_slug, self.branch_user, self.branch_pw)
        # demo-cat-25.png is PET-157 in 'main', absent in 'branch' -> must never return PET-157 or exact match
        self._submit_image_search(DEMO_PETS_DIR / "demo-cat-25.png", species="")
        self.assertEqual(self.page.locator('[data-match-tier="exact_image_match"]').count(), 0)
        self.assertEqual(self.page.locator('[data-pet-code="PET-157"]').count(), 0)

        photo_resp = self.page.goto(f"{self.base_url}/pets/photo/{self.main_pet157_photo}")
        self.assertIsNotNone(photo_resp)
        self.assertEqual(photo_resp.status, 404)

        self.context.clear_cookies()
        self._login("main", "staff1", DEMO_STAFF_PASSWORD)
        self._submit_image_search(DEMO_PETS_DIR / "demo-dog-01.png")
        self.assertEqual(
            self.page.locator(".visual-results-grid .pet-card").first.get_attribute("data-pet-code"),
            "PET-101",
        )
        new_resp = self.page.goto(f"{self.base_url}/pets/new")
        self.assertIsNotNone(new_resp)
        self.assertEqual(new_resp.status, 403)


if __name__ == "__main__":
    unittest.main()

"""Real-browser Vision workflow against a loopback-only OpenAI-compatible mock."""

from __future__ import annotations

import base64
import http.client
from io import BytesIO
import json
import os
import re
import socket
import subprocess  # nosec B404
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from PIL import Image
from playwright.sync_api import expect, sync_playwright

from scripts.demo.test_accounts import DEMO_ADMIN_PASSWORD, DEMO_STAFF_PASSWORD

from petcare.config import Config
from petcare.database.initialize import initialize_database
from petcare.database.seed import seed_database


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "vision"
AXE_CORE_JS = ROOT / "tests" / "a11y" / "node_modules" / "axe-core" / "axe.min.js"
ARTIFACT_DIR = Path(os.environ.get("PLAYWRIGHT_ARTIFACT_DIR") or (
    Path(tempfile.gettempdir()) / "petcare-phase52-browser"
)).resolve()
EMPTY_CREDENTIAL = ""
SEED_PASSWORDS = {
    "admin": DEMO_ADMIN_PASSWORD,
    "staff1": DEMO_STAFF_PASSWORD,
}


class _MockVisionState:
    lock = threading.Lock()
    mode = "valid"
    delay = 0.0
    images: list[dict] = []

    @classmethod
    def configure(cls, mode="valid", delay=0.0):
        with cls.lock:
            cls.mode = mode
            cls.delay = delay


class _MockVisionHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 8 * 1024 * 1024:
                self.send_error(413)
                return
            request = json.loads(self.rfile.read(length))
            message = request["messages"][-1]["content"]
            image_url = next(part["image_url"]["url"] for part in message if part.get("type") == "image_url")
            encoded = image_url.split(",", 1)[1]
            raw = base64.b64decode(encoded, validate=True)
            with Image.open(BytesIO(raw)) as image:
                image_info = {
                    "format": image.format,
                    "size": image.size,
                    "exif_count": len(image.getexif()),
                    "model": request.get("model"),
                }
            with _MockVisionState.lock:
                _MockVisionState.images.append(image_info)
                mode, delay = _MockVisionState.mode, _MockVisionState.delay
            if mode == "timeout":
                time.sleep(1.5)
            elif delay:
                time.sleep(delay)
            if mode == "unavailable":
                self._json(503, {"error": "mock provider unavailable"})
                return
            content = {
                "valid": json.dumps({
                    "species": "cat", "breed": "domestic shorthair", "coat_color": "black",
                    "coat_pattern": "solid", "coat_length": "short", "eye_color": "green",
                    "size": "small", "confidence": 0.99,
                    "url": "https://untrusted.example/", "html": "<script>never-run()</script>",
                }),
                "malformed": "not valid JSON",
                "ambiguous": json.dumps({"species": "", "breed": "", "confidence": 0.99}),
            }.get(mode, json.dumps({"species": "cat", "coat_color": "black"}))
            self._json(200, {"choices": [{"message": {"content": content}}]})
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
        except Exception:
            self._json(400, {"error": "invalid local mock request"})

    def _json(self, status, value):
        body = json.dumps(value).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class VisionBrowserE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_db = os.getenv("PETCARE_TEST_DB_NAME", "")
        if not re.fullmatch(r"[A-Za-z0-9_]+_test", test_db) or Config.DB_NAME != test_db:
            raise RuntimeError("Vision browser test requires DB_NAME=PETCARE_TEST_DB_NAME on an isolated _test schema.")
        if not os.getenv("PET_IMAGE_DIR"):
            raise RuntimeError("Vision browser test requires isolated PET_IMAGE_DIR storage.")
        if Path(os.environ["PET_IMAGE_DIR"]).resolve().is_relative_to(ROOT):
            raise RuntimeError("Vision browser test refuses pet-image storage inside the repository.")
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        ARTIFACT_DIR.chmod(0o700)
        initialize_database()
        seed_database()

        cls.mock_server = ThreadingHTTPServer(("127.0.0.1", 0), _MockVisionHandler)
        cls.mock_server.daemon_threads = True
        cls.mock_port = cls.mock_server.server_address[1]
        cls.mock_thread = threading.Thread(target=cls.mock_server.serve_forever, daemon=True)
        cls.mock_thread.start()

        cls.app_port = _free_port()
        cls.base_url = f"http://127.0.0.1:{cls.app_port}"
        child_env = os.environ.copy()
        child_env.update({
            "APP_ENV": "test",
            "APP_PORT": str(cls.app_port),
            "PUBLIC_BASE_URL": cls.base_url,
            "COOKIE_SECURE": "0",
            "LAN_ACCESS_ENABLED": "0",
            "AI_VISION_ENABLED": "1",
            "AI_API_BASE_URL": f"http://127.0.0.1:{cls.mock_port}/v1",
            "AI_API_KEY": EMPTY_CREDENTIAL,
            "AI_MODEL": "petcare-phase52-local-mock",
            "AI_TIMEOUT_SECONDS": "1",
            "AI_VISION_MAX_RETRIES": "1",
            "AI_TEST_ALLOW_LOOPBACK_PROVIDER": "1",
            "VISION_RATE_LIMIT_PER_MINUTE": "1000",
            "VISION_IP_RATE_LIMIT_PER_MINUTE": "1000",
            "IMAGE_PROCESSING_CONCURRENCY": "1",
            "MAIL_HOST": "",
            "MAIL_USERNAME": "",
            "MAIL_PASSWORD": EMPTY_CREDENTIAL,
            "MEDIA_STORAGE_BACKEND": "local",
            "TENANT_EXPORT_STORAGE_BACKEND": "local",
            "PRODUCT_IMAGE_DIR": str(ARTIFACT_DIR / "products"),
            "PET_IMAGE_DIR": os.environ["PET_IMAGE_DIR"],
            "TENANT_EXPORT_DIR": str(ARTIFACT_DIR / "exports"),
            "PLAYWRIGHT_ARTIFACT_DIR": str(ARTIFACT_DIR),
        })
        cls.runtime_log = (ARTIFACT_DIR / "vision-runtime.log").open("ab")
        os.chmod(cls.runtime_log.name, 0o600)
        cls.server = subprocess.Popen(  # nosec B603
            [sys.executable, str(ROOT / "run.py")], cwd=ROOT, env=child_env,
            stdout=cls.runtime_log, stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 35
        ready = False
        while time.monotonic() < deadline:
            if cls.server.poll() is not None:
                raise RuntimeError(f"Vision browser Flask process exited with {cls.server.returncode}.")
            try:
                probe = http.client.HTTPConnection("127.0.0.1", cls.app_port, timeout=1)
                try:
                    probe.request("GET", "/readyz")
                    response = probe.getresponse()
                    if response.status == 200:
                        ready = True
                        break
                finally:
                    probe.close()
            except OSError:
                pass
            time.sleep(0.2)
        if not ready:
            raise RuntimeError("Vision browser Flask process did not reach /readyz=200.")
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
        mock_server = getattr(cls, "mock_server", None)
        if mock_server:
            mock_server.shutdown()
            mock_server.server_close()
        thread = getattr(cls, "mock_thread", None)
        if thread:
            thread.join(timeout=5)

    def setUp(self):
        _MockVisionState.configure("valid")
        self.axe_results = {}
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 960}, locale="vi-VN", timezone_id="Asia/Ho_Chi_Minh")
        self.context.tracing.start(screenshots=True, snapshots=False, sources=False)
        self.page = self.context.new_page()
        self.page.set_default_timeout(10_000)
        self.page_errors = []
        self.failed_requests = []
        self.http_errors = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))

    def _run_axe(self, state):
        self.assertTrue(AXE_CORE_JS.is_file(), "Run npm ci --prefix tests/a11y before browser smoke tests.")
        self.assertTrue(self.page.evaluate("typeof axe === 'object'"), "axe-core must load before page scripts.")
        # Contrast evaluation should inspect settled controls, not their intentionally faded entrance frame.
        self.page.evaluate("document.getAnimations().forEach(animation => { try { animation.finish(); } catch (_) {} })")
        report = self.page.evaluate("""async () => {
          const result = await axe.run(document.querySelector('#main-content'), {
            runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']}
          });
          const summarize = rule => ({
            id: rule.id, impact: rule.impact, help: rule.help,
            nodes: rule.nodes.map(node => ({
              targets: node.target,
              checks: [...node.any, ...node.all, ...node.none].map(check => ({message:check.message, data:check.data}))
            }))
          });
          return {
            axe_version: axe.version,
            violations: result.violations.map(summarize),
            incomplete: result.incomplete.map(summarize)
          };
        }""")
        self.axe_results[state] = report
        result_path = ARTIFACT_DIR / "vision-accessibility-axe.json"
        result_path.write_text(json.dumps(self.axe_results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result_path.chmod(0o600)
        significant = [item for item in report["violations"] if item["impact"] in {"critical", "serious"}]
        self.assertEqual(significant, [], f"Axe critical/serious violations in {state}: {json.dumps(significant, ensure_ascii=False)}")
        self.page.on("requestfailed", lambda request: self.failed_requests.append(_path(request.url)))
        self.page.on("response", lambda response: self.http_errors.append((response.status, _path(response.url))) if response.status >= 400 else None)

    def tearDown(self):
        stem = re.sub(r"[^A-Za-z0-9_-]+", "_", self.id().split(".")[-1]).strip("_")
        if self.page and not self.page.is_closed():
            screenshot = ARTIFACT_DIR / f"{stem}-final.png"
            self.page.screenshot(path=str(screenshot), full_page=True, animations="disabled")
            screenshot.chmod(0o600)
        trace = ARTIFACT_DIR / f"{stem}-trace.zip"
        self.context.tracing.stop(path=str(trace))
        trace.chmod(0o600)
        self.context.close()
        diagnostics = ARTIFACT_DIR / f"{stem}-diagnostics.json"
        diagnostics.write_text(json.dumps({
            "http_errors": self.http_errors, "failed_requests": self.failed_requests,
            "page_errors": self.page_errors,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        diagnostics.chmod(0o600)
        self.assertEqual(self.failed_requests, [])
        self.assertEqual(self.page_errors, [])
        unexpected = [(status, path) for status, path in self.http_errors if status >= 500 or (status == 404 and path != "/favicon.ico")]
        self.assertEqual(unexpected, [])

    def _login(self, username="admin"):
        self.page.goto(self.base_url + "/login", wait_until="domcontentloaded")
        self.page.locator('input[name="store_slug"]').fill("main")
        self.page.locator('input[name="username"]').fill(username)
        self.page.locator('input[name="password"]').fill(SEED_PASSWORDS[username])
        self.page.locator('.login-card form button[type="submit"]').click()
        self.page.wait_for_url(self.base_url + "/dashboard")

    def _pet_form(self):
        self.page.goto(self.base_url + "/pets/new", wait_until="domcontentloaded")
        self.assertEqual(self.page.locator("main").count(), 1)
        photo = self.page.locator("[data-photo-input]")
        self.assertEqual(photo.evaluate("node => node.labels.length"), 1)
        self.assertEqual(self.page.locator("[data-attribute-status]").get_attribute("aria-live"), "polite")
        return photo

    def _choose(self, name, mime="image/png"):
        self.page.locator("[data-photo-input]").set_input_files({
            "name": name,
            "mimeType": mime,
            "buffer": (FIXTURES / name).read_bytes(),
        })

    def test_admin_gets_structured_suggestions_applies_only_blank_fields_and_fits_viewports(self):
        self._login()
        photo = self._pet_form()
        for width in (320, 390, 768, 820, 1024, 1440):
            self.page.set_viewport_size({"width": width, "height": 960})
            self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
        self.page.locator('input[name="coat_color"]').fill("operator-entered")
        _MockVisionState.configure("slow", delay=0.25)
        photo.set_input_files({"name": "synthetic-cat-black.png", "mimeType": "image/png", "buffer": (FIXTURES / "synthetic-cat-black.png").read_bytes()})
        status = self.page.locator("[data-attribute-status]")
        self.assertEqual(self.page.locator("[data-attribute-panel]").get_attribute("aria-busy"), "true")
        expect(status).to_contain_text("Đang đọc đặc điểm ảnh")
        expect(status).to_contain_text("Gợi ý ngoại hình")
        expect(self.page.locator("[data-attribute-values]")).to_contain_text("Loài: cat")
        expect(self.page.locator("[data-attribute-apply]")).to_be_visible()
        self.page.locator("[data-attribute-apply]").focus()
        self.page.keyboard.press("Enter")
        expect(self.page.locator('input[name="species"]')).to_have_value("cat")
        expect(self.page.locator('input[name="coat_color"]')).to_have_value("operator-entered")
        toast_close = self.page.locator(".toast-close")
        if toast_close.count():
            toast_close.first.click()
        self.page.set_viewport_size({"width": 390, "height": 844})
        mobile_screenshot = ARTIFACT_DIR / "vision-suggestions-390.png"
        self.page.screenshot(path=str(mobile_screenshot), full_page=True, animations="disabled")
        mobile_screenshot.chmod(0o600)
        self.page.set_viewport_size({"width": 1440, "height": 960})
        desktop_screenshot = ARTIFACT_DIR / "vision-suggestions-1440.png"
        self.page.screenshot(path=str(desktop_screenshot), full_page=True, animations="disabled")
        desktop_screenshot.chmod(0o600)
        self.assertTrue(_MockVisionState.images)
        self.assertEqual(_MockVisionState.images[-1]["format"], "JPEG")
        self.assertEqual(_MockVisionState.images[-1]["exif_count"], 0)

    def test_vision_keyboard_accessibility_axe_and_error_recovery_states(self):
        self.assertTrue(AXE_CORE_JS.is_file(), "Run npm ci --prefix tests/a11y before browser smoke tests.")
        self.page.add_init_script(path=str(AXE_CORE_JS))
        self._login()
        photo = self._pet_form()
        self._run_axe("empty_form")

        self.assertTrue(photo.evaluate("node => node.labels.length === 1"))
        for _ in range(60):
            self.page.keyboard.press("Tab")
            if photo.evaluate("node => document.activeElement === node"):
                break
        self.assertTrue(photo.evaluate("node => document.activeElement === node"), "Photo input must be reachable by keyboard.")
        focus = photo.evaluate("node => ({style:getComputedStyle(node).outlineStyle,width:getComputedStyle(node).outlineWidth})")
        self.assertNotEqual(focus["style"], "none")
        self.assertGreater(float(focus["width"].replace("px", "")), 0)

        # 720 CSS px is a 200%-equivalent layout viewport for a 1440 px desktop.
        # Playwright cannot set Chromium's browser chrome zoom, so this is recorded as a viewport simulation.
        self.page.set_viewport_size({"width": 720, "height": 960})
        self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), 720)
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.assertEqual(self.page.evaluate("document.documentElement.scrollWidth"), 390)
        self.page.set_viewport_size({"width": 1440, "height": 960})

        self._choose("synthetic-cat-black.png")
        status = self.page.locator("[data-attribute-status]")
        expect(status).to_contain_text("Gợi ý ngoại hình")
        self.assertEqual(status.get_attribute("role"), "status")
        self.assertEqual(status.get_attribute("aria-live"), "polite")
        self._run_axe("suggestions")

        dismiss = self.page.locator("[data-attribute-dismiss]")
        for _ in range(20):
            if dismiss.evaluate("node => document.activeElement === node"):
                break
            self.page.keyboard.press("Tab")
        self.assertTrue(dismiss.evaluate("node => document.activeElement === node"), "Dismiss control must be in keyboard focus order.")
        self.page.keyboard.press("Enter")
        expect(status).to_contain_text("Đã bỏ qua gợi ý")
        self.assertEqual(self.page.locator('input[name="species"]').input_value(), "")
        self._run_axe("dismissed")

        _MockVisionState.configure("unavailable")
        self._choose("synthetic-dog-brown.webp", "image/webp")
        expect(status).to_contain_text("Không kết nối được Vision")
        self._run_axe("provider_error")
        _MockVisionState.configure("valid")
        self.page.locator("[data-attribute-retry]").click()
        expect(status).to_contain_text("Gợi ý ngoại hình")
        self._run_axe("recovered")

    def test_upload_validation_uses_image_content_and_shows_inline_size_feedback(self):
        self._login()
        self._pet_form()
        status = self.page.locator("[data-attribute-status]")
        upload_status = self.page.locator("[data-photo-upload-status]")
        for name in ("unsupported.gif", "corrupted.png", "empty.bin"):
            mime = "image/gif" if name.endswith("gif") else "image/png"
            self._choose(name, mime)
            expect(status).to_have_text("Đang đọc đặc điểm ảnh…")
            expect(status).not_to_have_text("Đang đọc đặc điểm ảnh…", timeout=5_000)
            expect(status).to_contain_text("ảnh", timeout=5_000)
            expect(self.page.locator("[data-attribute-retry]")).to_be_hidden()

        # The extension and client MIME are untrusted; this contains valid PNG bytes.
        self._choose("extension-mismatch.jpg", "text/plain")
        expect(status).to_contain_text("Gợi ý ngoại hình", timeout=5_000)
        before = len(_MockVisionState.images)
        oversized = {"name": "oversized.png", "mimeType": "image/png", "buffer": b"0" * (5 * 1024 * 1024 + 1)}
        self.page.locator("[data-photo-input]").set_input_files(oversized)
        expect(upload_status).to_contain_text("5 MB")
        self.assertEqual(len(_MockVisionState.images), before)

        result = self.page.evaluate("""async () => {
          const body = new FormData();
          const response = await fetch('/pets/suggest-attributes', {
            method: 'POST', credentials: 'same-origin',
            headers: {'X-CSRFToken': document.querySelector('[name=csrf_token]').value}, body
          });
          return {status: response.status, json: await response.json()};
        }""")
        self.assertEqual(result["status"], 400)
        self.assertEqual(result["json"]["status"], "invalid_input")

    def test_provider_unavailable_malformed_ambiguous_and_manual_retry_states(self):
        self._login()
        self._pet_form()
        status = self.page.locator("[data-attribute-status]")
        _MockVisionState.configure("unavailable")
        self._choose("synthetic-cat-black.png")
        expect(status).to_contain_text("Không kết nối được Vision")
        retry = self.page.locator("[data-attribute-retry]")
        expect(retry).to_be_visible()
        _MockVisionState.configure("valid")
        retry.click()
        expect(status).to_contain_text("Gợi ý ngoại hình")

        _MockVisionState.configure("timeout")
        self._choose("synthetic-dog-brown.webp", "image/webp")
        expect(status).to_contain_text("Không kết nối được Vision", timeout=5_000)

        _MockVisionState.configure("malformed")
        self._choose("synthetic-cat-black.png")
        expect(status).to_contain_text("Ước lượng màu cục bộ")
        expect(retry).to_be_visible()
        _MockVisionState.configure("ambiguous")
        retry.click()
        expect(status).to_contain_text("Ước lượng màu cục bộ")
        self.assertTrue(self.page.locator("[data-attribute-apply]").is_visible())

    def test_staff_is_forbidden_and_concurrent_requests_are_bounded(self):
        self._login("staff1")
        self.page.goto(self.base_url + "/customers/new", wait_until="domcontentloaded")
        staff = self.page.evaluate("""async () => {
          const body = new FormData();
          body.append('photo', new Blob(['x'], {type:'image/png'}), 'x.png');
          const response = await fetch('/pets/suggest-attributes', {
            method: 'POST', credentials: 'same-origin',
            headers: {'X-CSRFToken': document.querySelector('[name=csrf_token]').value}, body
          });
          return {status: response.status, contentType: response.headers.get('content-type')};
        }""")
        self.assertEqual(staff["status"], 403)
        self.assertIn("text/html", staff["contentType"])

        self.context.clear_cookies()
        self._login("admin")
        self._pet_form()
        _MockVisionState.configure("slow", delay=0.4)
        encoded = base64.b64encode((FIXTURES / "synthetic-cat-black.png").read_bytes()).decode("ascii")
        outcomes = self.page.evaluate("""async encoded => {
          const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
          const token = document.querySelector('[name=csrf_token]').value;
          const send = async name => {
            const body = new FormData();
            body.append('photo', new Blob([bytes], {type:'image/png'}), name);
            const response = await fetch('/pets/suggest-attributes', {
              method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': token}, body
            });
            return {status: response.status, json: await response.json()};
          };
          return Promise.all([send('one.png'), send('two.png')]);
        }""", encoded)
        self.assertEqual(sorted(result["status"] for result in outcomes), [200, 429])
        self.assertEqual(next(result for result in outcomes if result["status"] == 429)["json"]["status"], "rate_limited")


def _path(url):
    return urlsplit(url).path

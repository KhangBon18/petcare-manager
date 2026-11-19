"""Run the local classroom workflow in Chromium, Firefox, and WebKit."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

from scripts.demo.test_accounts import DEMO_ADMIN_PASSWORD
from petcare.config import Config


ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("PETCARE_DEMO_BASE_URL", "").rstrip("/")
AXE_PATH = ROOT / "tests" / "a11y" / "node_modules" / "axe-core" / "axe.min.js"
VISION_IMAGE = ROOT / "tests" / "fixtures" / "vision" / "synthetic-cat-black.png"
SCREENSHOTS = ROOT / "docs" / "assets" / "phase62"


def _assert_safe_target():
    parsed = urlsplit(BASE_URL)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port:
        raise SystemExit("Set PETCARE_DEMO_BASE_URL to the local 127.0.0.1 QA app.")
    if os.environ.get("APP_ENV") != "test" or os.environ.get("PETCARE_DEMO_MODE") != "1":
        raise SystemExit("Cross-browser rehearsal requires explicit isolated QA mode.")
    if not Config.DB_NAME.endswith("_test") or Config.DB_HOST not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Refusing to rehearse against a non-local _test database.")
    if not AXE_PATH.is_file() or not VISION_IMAGE.is_file():
        raise SystemExit("Install the locked axe package and retain the synthetic Vision fixture.")


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _axe_scan(page, engine, label, records, axe_running):
    # axe-core inserts temporary inline styles. Keep WebKit's strict CSP check
    # free of that audit-tool instrumentation; structural checks still run there.
    if engine == "webkit":
        return
    axe_running["value"] = True
    page.evaluate("window.__petcareAxeScan = true")
    try:
        result = page.evaluate("""async () => {
          const result = await axe.run(document);
          await new Promise(resolve => setTimeout(resolve, 50));
          window.__petcareAxeScan = false;
          return result;
        }""")
    finally:
        page.evaluate("window.__petcareAxeScan = false")
        axe_running["value"] = False
    violations = [
        {"id": issue["id"], "impact": issue["impact"], "nodes": len(issue["nodes"])}
        for issue in result["violations"]
    ]
    records.append({
        "engine": engine,
        "state": label,
        "violations": violations,
        "incomplete_nodes": sum(len(issue["nodes"]) for issue in result["incomplete"]),
    })
    if violations:
        raise AssertionError(f"axe violations in {engine}/{label}: {violations}")


def _take_screenshot(page, path):
    page.evaluate("window.__petcareScreenshot = true")
    try:
        page.screenshot(path=str(path), full_page=False)
    finally:
        page.wait_for_timeout(50)
        page.evaluate("window.__petcareScreenshot = false")


def _login(page):
    response = page.goto(BASE_URL + "/login", wait_until="domcontentloaded")
    _require(bool(response and response.status == 200), "Local login page did not return HTTP 200.")
    page.locator('input[name="store_slug"]').fill("main")
    page.locator('input[name="username"]').fill("admin")
    page.locator('input[name="password"]').fill(DEMO_ADMIN_PASSWORD)
    page.locator('.login-card form button[type="submit"]').click()
    page.wait_for_url(BASE_URL + "/dashboard", timeout=10_000)


def _check_form_names(page):
    unnamed = page.evaluate("""() => [...document.querySelectorAll(
      'main input:not([type=hidden]):not([type=submit]), main select, main textarea'
    )].filter(el => {
      if (el.disabled || el.type === 'button') return false;
      const id = el.id;
      return !(el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') ||
        (id && document.querySelector(`label[for="${CSS.escape(id)}"]`)) || el.closest('label'));
    }).map(el => ({tag:el.tagName,type:el.type||'',name:el.name||'',id:el.id||''}))""")
    if unnamed:
        raise AssertionError(f"Unlabeled form fields: {unnamed}")


def _one_engine(name, browser_type, axe_records, screenshots):
    page_errors = []
    failed_requests = []
    http_errors = []
    csp_violations = []
    console_errors = []
    axe_running = {"value": False}
    started = time.monotonic()
    browser = browser_type.launch(headless=True)
    context = browser.new_context(viewport={"width": 390, "height": 844})
    context.add_init_script("""(() => {
      if (!sessionStorage.getItem('petcareCspViolations')) sessionStorage.setItem('petcareCspViolations', '[]');
      window.addEventListener('securitypolicyviolation', event => {
        const events = JSON.parse(sessionStorage.getItem('petcareCspViolations') || '[]');
        const target = event.target;
        events.push({
          directive:event.violatedDirective, blocked:event.blockedURI, source:event.sourceFile,
          target:target?.tagName || "", target_id:target?.id || "",
          target_class:typeof target?.className === "string" ? target.className : "",
          target_style:target?.getAttribute?.("style") || "",
          axe_scan:Boolean(window.__petcareAxeScan), screenshot:Boolean(window.__petcareScreenshot),
          path:location.pathname
        });
        sessionStorage.setItem('petcareCspViolations', JSON.stringify(events));
      });
    })();""")
    page = context.new_page()
    if name != "webkit":
        page.add_init_script(path=str(AXE_PATH))
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on("requestfailed", lambda request: failed_requests.append(request.url))
    def capture_console_error(message):
        if message.type != "error":
            return
        if axe_running["value"] and "style-src directive" in message.text:
            return
        console_errors.append(message.text)

    page.on("console", capture_console_error)
    page.on("response", lambda response: http_errors.append({"url": response.url, "status": response.status}) if response.status >= 400 and not response.url.endswith("/favicon.ico") else None)

    _login(page)
    expect(page.get_by_role("main")).to_be_visible()
    _take_screenshot(page, SCREENSHOTS / f"{name}-dashboard-390.png")
    screenshots.append(f"{name}-dashboard-390.png")
    _axe_scan(page, name, "dashboard", axe_records, axe_running)

    route_cases = (
        ("/customers/new", "customer form"),
        ("/pets/new", "pet form"),
        ("/products/new", "product form"),
        ("/invoices/new", "POS"),
        ("/purchasing/", "purchasing"),
        ("/reports/?period=month", "reports"),
    )
    for path, label in route_cases:
        response = page.goto(BASE_URL + path, wait_until="domcontentloaded")
        _require(bool(response and response.status == 200), f"{name} {path} did not return HTTP 200.")
        page.get_by_role("main").wait_for(state="visible")
        width = page.evaluate("document.documentElement.scrollWidth")
        _require(width <= 390, f"{name} {label} overflowed at 390px: {width}")
        if label.endswith("form"):
            _check_form_names(page)
        _axe_scan(page, name, label, axe_records, axe_running)
        if label == "POS":
            search = page.locator("[data-pos-search]")
            search.fill("FOOD-001")
            product = page.locator('button[data-pos-item][data-code="FOOD-001"]').first
            expect(product).to_be_visible(timeout=5_000)
            product.click()
            expect(page.locator(".invoice-line").first).to_be_visible()
            expect(page.locator("[data-pos-mobile-count]")).to_contain_text("1")
            _take_screenshot(page, SCREENSHOTS / f"{name}-pos-390.png")
            screenshots.append(f"{name}-pos-390.png")
            _axe_scan(page, name, "POS cart", axe_records, axe_running)
        if label == "reports":
            _take_screenshot(page, SCREENSHOTS / f"{name}-reports-390.png")
            screenshots.append(f"{name}-reports-390.png")
            expect(page.locator(".report-document")).to_be_visible()

    page.set_viewport_size({"width": 1440, "height": 960})
    response = page.goto(BASE_URL + "/products/?q=FOOD-001", wait_until="domcontentloaded")
    _require(bool(response and response.status == 200), f"{name} product inventory page did not return HTTP 200.")
    _require(page.evaluate("document.documentElement.scrollWidth") <= 1440, f"{name} product inventory overflowed at desktop.")
    _take_screenshot(page, SCREENSHOTS / f"{name}-products-1440.png")
    screenshots.append(f"{name}-products-1440.png")
    _axe_scan(page, name, "products", axe_records, axe_running)

    page.locator("#assistant-launcher").click()
    expect(page.locator("#assistant-panel")).to_be_visible()
    prompt_label = "Top products this week" if page.locator("html").get_attribute("lang") == "en" else "Bán chạy tuần này"
    prompt = page.locator("[data-assistant-prompt]").filter(has_text=prompt_label)
    expect(prompt).to_be_visible()
    prompt.click()
    expect(page.locator(".assistant-insight")).to_be_visible(timeout=10_000)
    expect(page.locator(".assistant-insight")).to_have_attribute("role", "group")
    _axe_scan(page, name, "assistant", axe_records, axe_running)

    page.goto(BASE_URL + "/pets/new", wait_until="domcontentloaded")
    page.locator('input[name="coat_color"]').fill("màu do người dùng nhập")
    page.locator('input[name="photo"]').set_input_files(str(VISION_IMAGE))
    apply = page.locator("[data-attribute-apply]")
    expect(apply).to_be_visible(timeout=10_000)
    _axe_scan(page, name, "vision suggestions", axe_records, axe_running)
    apply.focus()
    page.keyboard.press("Enter")
    expect(page.locator('input[name="species"]')).to_have_value("cat")
    expect(page.locator('input[name="coat_color"]')).to_have_value("màu do người dùng nhập")
    _require(page.url.endswith("/pets/new"), "Vision suggestions must not submit or save the pet form.")
    page.locator("[data-attribute-panel]").scroll_into_view_if_needed()
    page.set_viewport_size({"width": 390, "height": 844})
    _take_screenshot(page, SCREENSHOTS / f"{name}-vision-390.png")
    screenshots.append(f"{name}-vision-390.png")

    all_csp_violations = page.evaluate("JSON.parse(sessionStorage.getItem('petcareCspViolations') || '[]')")
    select_compat_events = [
        item for item in all_csp_violations
        if name == "webkit" and item["directive"] == "style-src-attr"
        and item["target"] == "SELECT" and not item["target_style"]
    ]
    screenshot_events = [item for item in all_csp_violations if item.get("screenshot")]
    csp_violations = [
        item for item in all_csp_violations
        if not item.get("axe_scan") and not item.get("screenshot") and item not in select_compat_events
    ]
    if name == "webkit":
        blocked_inline_styles = [item for item in csp_violations if item["directive"].startswith("style-src")]
        _require(not blocked_inline_styles, f"WebKit had blocked inline-style writes: {blocked_inline_styles}")
        csp_console = "Refused to apply a stylesheet because its hash, its nonce, or 'unsafe-inline' does not appear in the style-src directive of the Content Security Policy."
        expected_console_count = len(select_compat_events) + len(screenshot_events)
        for _ in range(expected_console_count):
            try:
                console_errors.remove(csp_console)
            except ValueError:
                break
    browser.close()
    if page_errors or failed_requests or http_errors or console_errors:
        raise AssertionError(json.dumps({
            "engine": name, "page_errors": page_errors, "failed_requests": failed_requests,
            "http_errors": http_errors, "console_errors": console_errors,
        }, ensure_ascii=False))
    return {
        "engine": name,
        "status": "PASS",
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "application_csp_violations": len(csp_violations),
        "axe_harness_csp_events": sum(bool(item.get("axe_scan")) for item in all_csp_violations),
        "automation_harness_csp_events": len(all_csp_violations) - len(csp_violations),
        "webkit_select_compat_events": len(select_compat_events),
        "screenshot_csp_events": len(screenshot_events),
    }


def main():
    _assert_safe_target()
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    screenshots = []
    axe_records = []
    results = []
    with sync_playwright() as playwright:
        for name, engine in (("chromium", playwright.chromium), ("firefox", playwright.firefox), ("webkit", playwright.webkit)):
            results.append(_one_engine(name, engine, axe_records, screenshots))
    report = {
        "status": "PASS",
        "engines": results,
        "axe_scans": len(axe_records),
        "axe_violations": sum(len(item["violations"]) for item in axe_records),
        "axe_incomplete_nodes": sum(item["incomplete_nodes"] for item in axe_records),
        "screenshots": screenshots,
    }
    output = Path(os.environ.get(
        "PETCARE_DEMO_REHEARSAL_REPORT",
        str(Path(tempfile.gettempdir()) / "petcare-phase62-cross-browser.json"),
    ))
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output.chmod(0o600)
    print(json.dumps(report, ensure_ascii=False))
    print(f"Report: {output}")


if __name__ == "__main__":
    main()

"""Accessibility, overflow and keyboard-focus audit for redesigned PetCare screens.

Runs axe-core (WCAG 2.0/2.1 A+AA, serious/critical) on real rendered pages at
desktop and mobile widths, checks for horizontal overflow, and verifies that the
first keyboard Tab stops expose a visible focus indicator.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
AXE = ROOT / "tests" / "a11y" / "node_modules" / "axe-core" / "axe.min.js"
BASE = os.environ.get("PETCARE_UI_BASE_URL", "http://127.0.0.1:5055").rstrip("/")
PAGES = ["/dashboard", "/invoices/new", "/products/", "/customers/", "/pets/", "/pets/find-similar",
         "/assistant/chat", "/invoices/", "/reports/", "/users/", "/store/settings", "/pets/new"]
VIEWPORTS = {"desktop": (1440, 900), "tablet": (834, 1112), "mobile": (390, 844)}

AXE_RUN = """async () => {
  const r = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa']}});
  return r.violations.filter(v => ['serious','critical'].includes(v.impact))
    .map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.length, sample: v.nodes[0] && v.nodes[0].target.join(' ')}));
}"""

FOCUS_PROBE = """() => {
  const el = document.activeElement; if (!el || el === document.body) return null;
  const cs = getComputedStyle(el);
  const visible = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || cs.boxShadow !== 'none';
  return {tag: el.tagName, text: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 40), visible};
}"""


def main() -> int:
    password = os.environ["PETCARE_UI_ADMIN_PASSWORD"]
    report = {"axe": {}, "overflow": [], "focus": {}}
    failures = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        # Anonymous login page
        for vp, (w, h) in VIEWPORTS.items():
            ctx = browser.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce")
            ctx.add_init_script(path=str(AXE))
            page = ctx.new_page()
            page.goto(BASE + "/login", wait_until="networkidle")
            v = page.evaluate(AXE_RUN)
            report["axe"][f"/login@{vp}"] = v
            failures += len(v)
            if page.evaluate("document.documentElement.scrollWidth") > w:
                report["overflow"].append(f"/login@{vp}")
            ctx.close()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        ctx.add_init_script(path=str(AXE))
        page = ctx.new_page()
        page.goto(BASE + "/login", wait_until="domcontentloaded")
        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', password)
        with page.expect_navigation():
            page.click('.login-card button[type="submit"]')
        for path in PAGES:
            for vp, (w, h) in VIEWPORTS.items():
                page.set_viewport_size({"width": w, "height": h})
                page.goto(BASE + path, wait_until="networkidle")
                v = page.evaluate(AXE_RUN)
                report["axe"][f"{path}@{vp}"] = v
                failures += len(v)
                if page.evaluate("document.documentElement.scrollWidth") > w:
                    report["overflow"].append(f"{path}@{vp}")
                    failures += 1
            page.set_viewport_size({"width": 1440, "height": 900})
            page.goto(BASE + path, wait_until="networkidle")
            stops = []
            for _ in range(6):
                page.keyboard.press("Tab")
                info = page.evaluate(FOCUS_PROBE)
                if info:
                    stops.append(info)
                    if not info["visible"]:
                        failures += 1
            report["focus"][path] = stops
        browser.close()
    print(json.dumps({k: v for k, v in report["axe"].items() if v}, ensure_ascii=False, indent=1))
    print("overflow:", report["overflow"])
    invisible = {p: [s for s in st if not s["visible"]] for p, st in report["focus"].items()}
    print("focus without visible indicator:", {p: s for p, s in invisible.items() if s})
    print("pages x viewports checked:", len(report["axe"]), "| failures:", failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())


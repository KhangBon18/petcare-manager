"""Capture real rendered PetCare Manager screens for UI/UX before/after review.

Usage (against an isolated *_test demo server):
    PETCARE_UI_BASE_URL=http://127.0.0.1:5055 \
    PETCARE_UI_ADMIN_PASSWORD=... \
    python scripts/ui_capture/capture_screens.py --label before

Screenshots are written outside the repository by default; only curated
images should be copied into docs/assets.
"""

from __future__ import annotations

import argparse
import os
import re
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900},
    "tablet": {"width": 834, "height": 1112},
    "mobile": {"width": 390, "height": 844},
}

# (slug, path, viewports)
ALL = tuple(VIEWPORTS)
SCREENS = (
    ("02-dashboard", "/dashboard", ALL),
    ("03-pos", "/invoices/new", ALL),
    ("04-products", "/products/", ALL),
    ("05-inventory-product-detail", "/products/{product_id}", ("desktop",)),
    ("06-purchasing", "/purchasing/", ("desktop", "mobile")),
    ("07-customers", "/customers/", ALL),
    ("07b-customer-detail", "/customers/{customer_id}", ("desktop",)),
    ("08-pets", "/pets/", ALL),
    ("09-pet-detail-gallery", "/pets/{pet_id}", ("desktop", "mobile")),
    ("10-image-search", "/pets/find-similar", ("desktop", "mobile")),
    ("11-assistant", "/assistant/chat", ("desktop", "mobile")),
    ("12-invoices", "/invoices/", ("desktop", "mobile")),
    ("12b-invoice-detail", "/invoices/{invoice_id}", ("desktop",)),
    ("13-reports", "/reports/", ("desktop", "mobile")),
    ("14-users", "/users/", ("desktop",)),
    ("15-store-settings", "/store/settings", ("desktop",)),
    ("15b-account-settings", "/account/settings", ("desktop",)),
    ("16-activity", "/activity/", ("desktop",)),
    ("17-pet-form", "/pets/new", ("desktop",)),
    ("17b-product-form", "/products/new", ("desktop",)),
)


def _first_id(page, base, list_path, pattern):
    page.goto(base + list_path, wait_until="domcontentloaded")
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
    for href in hrefs:
        m = re.fullmatch(pattern, href or "")
        if m:
            return m.group(1)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "petcare-ui"))
    parser.add_argument("--only", default="", help="comma separated slug prefixes")
    args = parser.parse_args()
    base = os.environ.get("PETCARE_UI_BASE_URL", "http://127.0.0.1:5055").rstrip("/")
    password = os.environ["PETCARE_UI_ADMIN_PASSWORD"]
    out = Path(args.out) / args.label
    out.mkdir(parents=True, exist_ok=True)
    only = tuple(s for s in args.only.split(",") if s)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        # Login screen (anonymous)
        for vp_name, vp in VIEWPORTS.items():
            if only and not any("01-login".startswith(o) for o in only):
                break
            ctx = browser.new_context(viewport=vp, locale="vi-VN", reduced_motion="reduce")
            page = ctx.new_page()
            page.goto(base + "/login", wait_until="networkidle")
            page.screenshot(path=str(out / f"01-login-{vp_name}.png"), full_page=True)
            ctx.close()

        ctx = browser.new_context(viewport=VIEWPORTS["desktop"], locale="vi-VN", reduced_motion="reduce")
        page = ctx.new_page()
        page.goto(base + "/login", wait_until="domcontentloaded")
        page.fill('input[name="store_slug"]', "main")
        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', password)
        with page.expect_navigation():
            page.click('.login-card form button[type="submit"]')
        ids = {
            "product_id": _first_id(page, base, "/products/", r"/products/(\d+)"),
            "customer_id": _first_id(page, base, "/customers/", r"/customers/(\d+)"),
            "pet_id": _first_id(page, base, "/pets/", r"/pets/(\d+)"),
            "invoice_id": _first_id(page, base, "/invoices/", r"/invoices/(\d+)"),
        }
        for slug, path, vps in SCREENS:
            if only and not any(slug.startswith(o) for o in only):
                continue
            try:
                url = base + path.format(**ids)
            except (KeyError, TypeError):
                continue
            for vp_name in vps:
                page.set_viewport_size(VIEWPORTS[vp_name])
                page.goto(url, wait_until="networkidle")
                page.wait_for_timeout(250)
                page.screenshot(path=str(out / f"{slug}-{vp_name}.png"), full_page=True)
        ctx.close()
        browser.close()
    print(f"Saved screenshots to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


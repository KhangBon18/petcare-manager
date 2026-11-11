"""Run one connected, UI-driven classroom scenario against disposable QA MySQL."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlsplit
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

from scripts.demo.test_accounts import DEMO_ADMIN_PASSWORD, DEMO_STAFF_PASSWORD
from petcare.config import Config
from petcare.database.connection import get_connection
from petcare.repositories.base import fetch_one


ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("PETCARE_DEMO_BASE_URL", "").rstrip("/")
VISION_IMAGE = ROOT / "tests" / "fixtures" / "vision" / "synthetic-cat-black.png"
OUTPUT = Path(os.environ.get(
    "PETCARE_CLASSROOM_REHEARSAL_REPORT",
    str(Path(tempfile.gettempdir()) / "petcare-phase62-classroom-rehearsal.json"),
))


def _check_target():
    parsed = urlsplit(BASE_URL)
    if (parsed.scheme, parsed.hostname) != ("http", "127.0.0.1") or not parsed.port:
        raise SystemExit("Set PETCARE_DEMO_BASE_URL to the loopback QA application.")
    if os.environ.get("APP_ENV") != "test" or os.environ.get("PETCARE_DEMO_MODE") != "1":
        raise SystemExit("Classroom rehearsal requires explicit isolated QA mode.")
    if Config.DB_HOST not in {"127.0.0.1", "localhost"} or not Config.DB_NAME.endswith("_test"):
        raise SystemExit("Refusing to rehearse against a non-local _test database.")
    if not VISION_IMAGE.is_file():
        raise SystemExit("The synthetic Vision image fixture is missing.")


def _login(page, username, password):
    response = page.goto(BASE_URL + "/login", wait_until="domcontentloaded")
    if not response or response.status != 200:
        raise AssertionError("Login page did not return HTTP 200.")
    page.locator('input[name="store_slug"]').fill("main")
    page.locator('input[name="username"]').fill(username)
    page.locator('input[name="password"]').fill(password)
    page.locator('.login-card form button[type="submit"]').click()
    page.wait_for_url(BASE_URL + "/dashboard", timeout=10_000)


def _capture(page, screenshots, name):
    path = ROOT / "docs" / "assets" / "phase62" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=False)
    screenshots.append(name)


def _run():
    _check_target()
    started = time.monotonic()
    suffix = uuid4().hex[:8].upper()
    customer_name = f"QA Demo Buyer {suffix}"
    pet_code = f"DEMO-PET-{suffix}"
    pet_name = f"Miu {suffix[:4]}"
    product_code = f"DEMO-FOOD-{suffix}"
    product_name = f"QA Demo Cat Food {suffix}"
    supplier_name = f"QA Demo Supplier {suffix}"
    phone = "09" + f"{uuid4().int % 100_000_000:08d}"
    screenshots = []
    diagnostics = {"page_errors": [], "failed_requests": [], "expected_download_request_events": [], "http_errors": [], "console_errors": []}
    results = {"steps": []}

    with get_connection() as connection:
        tenant = fetch_one(connection, "SELECT id FROM tenants WHERE slug = %s", ("main",))
        admin = fetch_one(connection, "SELECT id FROM users WHERE username = %s", ("admin",))
    if not tenant or not admin:
        raise AssertionError("The expected isolated QA tenant/admin seed is missing.")
    tenant_id = tenant["id"]
    admin_id = admin["id"]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 960}, accept_downloads=True)
        page = context.new_page()
        page.on("pageerror", lambda error: diagnostics["page_errors"].append(str(error)))
        def record_failed_request(request):
            request_path = urlsplit(request.url).path
            if re.fullmatch(r"/users/export/jobs/\d+/download", request_path):
                diagnostics["expected_download_request_events"].append(request_path)
            else:
                diagnostics["failed_requests"].append(request.url)

        page.on("requestfailed", record_failed_request)
        page.on("console", lambda message: diagnostics["console_errors"].append(message.text) if message.type == "error" else None)
        def record_http_error(response):
            expected_staff_denial = "/users/" in response.url and response.status == 403
            if response.status >= 400 and not response.url.endswith("/favicon.ico") and not expected_staff_denial:
                diagnostics["http_errors"].append({"url": response.url, "status": response.status})

        page.on("response", record_http_error)

        _login(page, "admin", DEMO_ADMIN_PASSWORD)
        expect(page.get_by_role("heading", level=1)).to_be_visible()
        _capture(page, screenshots, "classroom-dashboard.png")
        results["steps"].append("admin login and role view")

        page.goto(BASE_URL + "/customers/new", wait_until="domcontentloaded")
        page.locator("#full_name").fill(customer_name)
        page.locator("#phone").fill(phone)
        page.locator("#address").fill("Synthetic classroom data")
        page.locator('.form-card form button[type="submit"]').click()
        page.wait_for_url(BASE_URL + "/customers/")
        expect(page.locator(".flash-success")).to_be_visible()
        with get_connection() as connection:
            customer = fetch_one(connection, "SELECT id FROM customers WHERE tenant_id=%s AND full_name=%s", (tenant_id, customer_name))
        if not customer:
            raise AssertionError("Created customer was not persisted in QA MySQL.")
        customer_id = customer["id"]
        results["steps"].append("create synthetic customer")

        page.goto(BASE_URL + "/pets/new", wait_until="domcontentloaded")
        for name, value in {
            "code": pet_code, "name": pet_name, "species": "cat", "breed": "domestic shorthair",
            "sale_price": "2500000", "coat_color": "black", "eye_color": "green",
        }.items():
            page.locator(f'input[name="{name}"]').fill(value)
        page.locator('.form-card form button.button-primary').click()
        page.wait_for_url(BASE_URL + "/pets/")
        expect(page.locator(".flash-success")).to_be_visible()
        with get_connection() as connection:
            pet = fetch_one(connection, "SELECT id FROM pets WHERE tenant_id=%s AND code=%s", (tenant_id, pet_code))
        if not pet:
            raise AssertionError("Created pet was not persisted in QA MySQL.")
        pet_id = pet["id"]
        results["steps"].append("register synthetic pet for sale")

        page.goto(BASE_URL + "/products/new", wait_until="domcontentloaded")
        for name, value in {
            "code": product_code, "name": product_name, "category": "QA demo",
            "unit_price": "75000", "reorder_level": "2", "stock_qty": "0",
        }.items():
            page.locator(f'input[name="{name}"]').fill(value)
        page.locator('.form-card form button.button-primary').click()
        page.wait_for_url(BASE_URL + "/products/")
        expect(page.locator(".flash-success")).to_be_visible()
        with get_connection() as connection:
            product = fetch_one(connection, "SELECT id,stock_qty FROM products WHERE tenant_id=%s AND code=%s", (tenant_id, product_code))
        if not product or product["stock_qty"] != 0:
            raise AssertionError("Created product did not persist with the requested zero stock.")
        product_id = product["id"]
        results["steps"].append("create zero-stock product")

        page.goto(BASE_URL + "/purchasing/suppliers/new", wait_until="domcontentloaded")
        page.locator('input[name="name"]').fill(supplier_name)
        page.locator('input[name="contact_name"]').fill("QA contact")
        page.locator('input[name="phone"]').fill(phone)
        page.locator('input[name="email"]').fill(f"qa-{suffix.lower()}@example.invalid")
        page.locator('.supplier-form-card form button.button-primary').click()
        page.wait_for_url(BASE_URL + "/purchasing/suppliers")
        expect(page.locator(".flash-success")).to_be_visible()
        with get_connection() as connection:
            supplier = fetch_one(connection, "SELECT id FROM suppliers WHERE tenant_id=%s AND name=%s", (tenant_id, supplier_name))
        if not supplier:
            raise AssertionError("Created supplier was not persisted in QA MySQL.")
        supplier_id = supplier["id"]
        results["steps"].append("create supplier")

        page.goto(BASE_URL + "/purchasing/new", wait_until="domcontentloaded")
        page.locator('select[name="supplier_id"]').select_option(str(supplier_id))
        page.locator("[data-product-query]").fill(product_code)
        add_product = page.locator(f'[data-add-product][data-product-code="{product_code}"]')
        expect(add_product).to_be_visible()
        add_product.click()
        line = page.locator("[data-order-line]")
        line.locator('input[name="quantity[]"]').fill("8")
        line.locator('input[name="unit_cost[]"]').fill("40000")
        page.locator('form[data-purchase-form] button[type="submit"]').click()
        page.wait_for_url(re.compile(r"/purchasing/\d+$"))
        order_id = int(page.url.rstrip("/").split("/")[-1])
        expect(page.locator(".purchasing-detail-heading")).to_be_visible()
        _capture(page, screenshots, "classroom-purchase-order.png")
        with get_connection() as connection:
            order = fetch_one(connection, "SELECT status FROM purchase_orders WHERE tenant_id=%s AND id=%s", (tenant_id, order_id))
            initial_stock = fetch_one(connection, "SELECT stock_qty FROM products WHERE tenant_id=%s AND id=%s", (tenant_id, product_id))["stock_qty"]
        if order["status"] != "ordered" or initial_stock != 0:
            raise AssertionError("Creating the purchase order must not mutate on-hand stock.")
        results["steps"].append("create purchase order; stock unchanged")

        receive = page.locator("[data-purchase-receive-form]")
        receive.locator('input[name="quantity[]"]').fill("3")
        receive.locator('button[type="submit"]').click()
        expect(page.locator(".flash-success")).to_be_visible()
        with get_connection() as connection:
            partial = fetch_one(connection, "SELECT status FROM purchase_orders WHERE tenant_id=%s AND id=%s", (tenant_id, order_id))["status"]
            partial_stock = fetch_one(connection, "SELECT stock_qty FROM products WHERE tenant_id=%s AND id=%s", (tenant_id, product_id))["stock_qty"]
        if (partial, partial_stock) != ("partially_received", 3):
            raise AssertionError("Partial receipt did not reconcile with stock and order state.")
        page.locator("[data-fill-remaining]").click()
        receive.locator('button[type="submit"]').click()
        expect(page.locator(".flash-success")).to_be_visible()
        with get_connection() as connection:
            final_order = fetch_one(connection, "SELECT status FROM purchase_orders WHERE tenant_id=%s AND id=%s", (tenant_id, order_id))["status"]
            received_stock = fetch_one(connection, "SELECT stock_qty FROM products WHERE tenant_id=%s AND id=%s", (tenant_id, product_id))["stock_qty"]
            receipt_movements = fetch_one(connection, "SELECT COUNT(*) AS total FROM stock_movements WHERE tenant_id=%s AND purchase_order_id=%s", (tenant_id, order_id))["total"]
        if (final_order, received_stock, receipt_movements) != ("received", 8, 2):
            raise AssertionError("Full receipt did not reconcile with PO state, stock and ledger.")
        results["steps"].append("partially receive 3, then receive remaining 5")

        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(BASE_URL + f"/invoices/new?customer_id={customer_id}", wait_until="domcontentloaded")
        expect(page.locator("#customer_id")).to_have_value(str(customer_id))
        page.locator("[data-pos-search]").fill(product_code)
        product_card = page.locator(f'button[data-pos-item][data-code="{product_code}"]')
        expect(product_card).to_be_visible()
        product_card.click()
        page.locator('[data-pos-filter="pet"]').click()
        page.locator("[data-pos-search]").fill(pet_code)
        pet_card = page.locator(f'button[data-pos-item][data-selection="pet:{pet_id}"]')
        expect(pet_card).to_be_visible()
        pet_card.click()
        product_quantity = page.locator('.invoice-line input[name="quantity"]').first
        product_quantity.fill("2")
        page.locator("#invoice-submit").click()
        page.wait_for_url(re.compile(r"/invoices/\d+$"))
        invoice_id = int(page.url.rstrip("/").split("/")[-1])
        expect(page.locator("body.invoice-detail-page")).to_contain_text(product_name)
        expect(page.locator("body.invoice-detail-page")).to_contain_text(pet_name)
        _capture(page, screenshots, "classroom-invoice.png")
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name=re.compile("Xác nhận thanh toán|Confirm payment")).click()
        expect(page.locator(".flash-success")).to_be_visible()
        with get_connection() as connection:
            invoice = fetch_one(connection, "SELECT i.status,COALESCE((SELECT SUM(ii.line_total) FROM invoice_items ii WHERE ii.tenant_id=i.tenant_id AND ii.invoice_id=i.id),0) AS total_amount FROM invoices i WHERE i.tenant_id=%s AND i.id=%s", (tenant_id, invoice_id))
            sale_stock = fetch_one(connection, "SELECT stock_qty FROM products WHERE tenant_id=%s AND id=%s", (tenant_id, product_id))["stock_qty"]
            pet_owner = fetch_one(connection, "SELECT buyer_id FROM pets WHERE tenant_id=%s AND id=%s", (tenant_id, pet_id))["buyer_id"]
        if invoice["status"] != "paid" or invoice["total_amount"] != 2650000 or sale_stock != 6 or pet_owner != customer_id:
            raise AssertionError("Paid invoice, product stock, pet ownership and customer did not reconcile.")
        results["steps"].append("POS sale links customer, product and pet; payment updates stock/ownership")

        page.goto(BASE_URL + f"/invoices/{invoice_id}", wait_until="domcontentloaded")
        product_item = page.locator(".refund-line").filter(has_text=product_name)
        expect(product_item).to_be_visible()
        item_id = int(product_item.locator('input[type="hidden"][name="invoice_item_id"]').input_value())
        page.locator(f'input[name="quantity_{item_id}"]').fill("1")
        page.locator(f'select[name="disposition_{item_id}"]').select_option("resell")
        refund_form = page.locator(".refund-form")
        page.once("dialog", lambda dialog: dialog.accept())
        refund_form.locator('button[type="submit"]').click()
        expect(page.locator(".flash-success")).to_be_visible()
        with get_connection() as connection:
            refund = fetch_one(connection, "SELECT refund_total FROM invoice_refunds WHERE tenant_id=%s AND invoice_id=%s ORDER BY id DESC LIMIT 1", (tenant_id, invoice_id))
            refunded_stock = fetch_one(connection, "SELECT stock_qty FROM products WHERE tenant_id=%s AND id=%s", (tenant_id, product_id))["stock_qty"]
            refunded_line = fetch_one(connection, "SELECT COALESCE(SUM(quantity), 0) AS quantity_refunded FROM invoice_refund_items WHERE tenant_id=%s AND invoice_id=%s AND invoice_item_id=%s", (tenant_id, invoice_id, item_id))["quantity_refunded"]
        if not refund or refund["refund_total"] != 75000 or (refunded_stock, refunded_line) != (7, 1):
            raise AssertionError("Partial refund ledger and restocked unit did not reconcile.")
        _capture(page, screenshots, "classroom-refund.png")
        results["steps"].append("record one-unit partial refund; restock and net line reconcile")

        page.goto(BASE_URL + "/reports/?period=month", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name=re.compile("Báo cáo|Reports")).first).to_be_visible()
        expect(page.locator(".report-document")).to_contain_text(product_name)
        _capture(page, screenshots, "classroom-report.png")
        results["steps"].append("verify financial and inventory report")

        page.goto(BASE_URL + "/users/export", wait_until="domcontentloaded")
        page.get_by_label(re.compile("Mật khẩu hiện tại|Current password")).fill(DEMO_ADMIN_PASSWORD)
        passphrase = "QA-" + uuid4().hex + "-passphrase"
        page.get_by_label(re.compile("Passphrase mã hóa|Encryption passphrase")).fill(passphrase)
        page.get_by_label(re.compile("Xác nhận passphrase|Confirm passphrase")).fill(passphrase)
        page.locator('[aria-labelledby="export-title"] form button[type="submit"]').click()
        page.wait_for_url(re.compile(r"/users/export/jobs/\d+$"))
        export_job_id = int(page.url.rstrip("/").split("/")[-1])
        page.wait_for_function("""async () => {
          const root = document.querySelector('[data-export-job]');
          if (!root) return false;
          const response = await fetch(root.dataset.statusUrl, {credentials:'same-origin', cache:'no-store'});
          if (!response.ok) return false;
          const state = await response.json();
          return state.status === 'ready';
        }""", timeout=90_000)
        expect(page.locator("#export-download")).to_be_visible(timeout=10_000)
        with page.expect_download() as download_info:
            page.locator("#export-download").click()
        download = download_info.value
        if not download.suggested_filename.endswith(".pcarexport"):
            raise AssertionError("Tenant export download did not have its encrypted artifact extension.")
        results["export_job_id"] = export_job_id
        results["steps"].append("QA tenant export worker reached ready and browser downloaded encrypted artifact")

        page.goto(BASE_URL + "/dashboard", wait_until="domcontentloaded")
        page.locator("#assistant-launcher").click()
        prompt_label = "Top products this week" if page.locator("html").get_attribute("lang") == "en" else "Bán chạy tuần này"
        page.locator("[data-assistant-prompt]").filter(has_text=prompt_label).click()
        expect(page.locator(".assistant-insight")).to_be_visible(timeout=10_000)
        expect(page.locator(".assistant-insight")).to_contain_text(product_code)
        _capture(page, screenshots, "classroom-assistant.png")
        results["steps"].append("Assistant top-products insight reflects the linked paid/refunded sale")

        page.goto(BASE_URL + "/pets/new", wait_until="domcontentloaded")
        page.locator('input[name="coat_color"]').fill("manual value retained")
        page.locator('input[name="photo"]').set_input_files(str(VISION_IMAGE))
        apply_suggestions = page.locator("[data-attribute-apply]")
        expect(apply_suggestions).to_be_visible(timeout=10_000)
        apply_suggestions.click()
        expect(page.locator('input[name="species"]')).to_have_value("cat")
        expect(page.locator('input[name="coat_color"]')).to_have_value("manual value retained")
        expect(page).to_have_url(re.compile(r"/pets/new$"))
        _capture(page, screenshots, "classroom-vision-mock.png")
        results["steps"].append("Vision mock suggestion is reviewed/applied only to blank fields; form is not saved")

        staff_context = browser.new_context(viewport={"width": 1440, "height": 960})
        staff_page = staff_context.new_page()
        _login(staff_page, "staff1", DEMO_STAFF_PASSWORD)
        allowed = staff_page.goto(BASE_URL + "/customers/", wait_until="domcontentloaded")
        forbidden = staff_page.goto(BASE_URL + "/users/", wait_until="domcontentloaded")
        if not allowed or allowed.status != 200 or not forbidden or forbidden.status != 403:
            raise AssertionError("Staff role did not match the documented customer/admin-export permissions.")
        results["steps"].append("staff role allowed customer access and was denied admin user/export route")
        staff_context.close()

        with get_connection() as connection:
            final = fetch_one(connection, """
                SELECT p.stock_qty, i.status AS invoice_status,
                       COALESCE((SELECT SUM(ii.line_total) FROM invoice_items ii WHERE ii.tenant_id=i.tenant_id AND ii.invoice_id=i.id), 0) AS total_amount,
                       COALESCE((SELECT SUM(ir.refund_total) FROM invoice_refunds ir WHERE ir.tenant_id=i.tenant_id AND ir.invoice_id=i.id), 0) AS total_refunded,
                       COALESCE((SELECT SUM(ii.line_total) FROM invoice_items ii WHERE ii.tenant_id=i.tenant_id AND ii.invoice_id=i.id), 0) - COALESCE((SELECT SUM(ir.refund_total) FROM invoice_refunds ir WHERE ir.tenant_id=i.tenant_id AND ir.invoice_id=i.id), 0) AS net_paid,
                       i.customer_id, pet.buyer_id AS pet_customer_id,
                       po.status AS po_status,
                       (SELECT COUNT(*) FROM stock_movements sm WHERE sm.tenant_id=p.tenant_id AND sm.purchase_order_id=po.id) AS receipt_movements
                FROM products p
                JOIN invoices i ON i.tenant_id=p.tenant_id AND i.id=%s
                JOIN pets pet ON pet.tenant_id=p.tenant_id AND pet.id=%s
                JOIN purchase_orders po ON po.tenant_id=p.tenant_id AND po.id=%s
                WHERE p.tenant_id=%s AND p.id=%s
            """, (invoice_id, pet_id, order_id, tenant_id, product_id))
        if not final or (final["stock_qty"], final["invoice_status"], final["total_amount"],
                         final["total_refunded"], final["net_paid"], final["customer_id"],
                         final["pet_customer_id"], final["po_status"], final["receipt_movements"]) != (
                            7, "paid", 2650000, 75000, 2575000, customer_id, customer_id, "received", 2):
            raise AssertionError(f"Final linked QA records did not reconcile: {final}")
        results["linked_records"] = {
            "customer_id": customer_id, "pet_id": pet_id, "product_id": product_id,
            "supplier_id": supplier_id, "purchase_order_id": order_id, "invoice_id": invoice_id,
            "product_stock_after_partial_refund": final["stock_qty"],
            "invoice_total": str(final["total_amount"]), "refunded": str(final["total_refunded"]),
            "net_paid": str(final["net_paid"]), "po_status": final["po_status"],
        }
        _require_no_unexpected_diagnostics(diagnostics)
        browser.close()

    results["status"] = "PASS"
    results["elapsed_seconds"] = round(time.monotonic() - started, 2)
    results["steps_completed"] = len(results["steps"])
    results["screenshots"] = screenshots
    results["diagnostics"] = diagnostics
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUTPUT.chmod(0o600)
    return results


def _require_no_unexpected_diagnostics(diagnostics):
    unexpected = {
        key: value for key, value in diagnostics.items()
        if key != "expected_download_request_events" and value
    }
    if unexpected:
        raise AssertionError(json.dumps(unexpected, ensure_ascii=False))


if __name__ == "__main__":
    report = _run()
    print(json.dumps(report, ensure_ascii=False))
    print(f"Report: {OUTPUT}")

"""Bounded local preflight: validate demo data and only refresh existing paid markers."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import hmac
from pathlib import Path
# Only a fixed Python worker is launched, without shell or user-supplied commands.
import subprocess  # nosec B404
import sys
from time import monotonic
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

import mysql.connector

from petcare.config import Config, mysql_config
from petcare.money import format_money
from petcare.database.seed import DEMO_SALES
from petcare.routes.health_routes import (
    demo_database_signature,
    schema_contract_is_ready,
)
from petcare.timezones import tenant_today
from petcare.vision.media_storage import get_media_storage

BUDGET_SECONDS = 4.7


class DemoNotReady(RuntimeError):
    """Actionable preflight failure, safe to print without credentials."""


def _fetch(cursor, sql, params=()):
    cursor.execute(sql, params)
    return cursor.fetchall()


def _web_ready(settings):
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, new_url):
            return None

    url = f"http://127.0.0.1:{settings.APP_PORT}"
    try:
        opener = build_opener(ProxyHandler({}), NoRedirect())
        with opener.open(url + "/readyz", timeout=1) as response:
            payload = json.loads(response.read(4097).decode("utf-8"))
            if response.status != 200 or payload != {"status": "ready"}:
                raise DemoNotReady("Web chưa ready. Kiểm tra server và /readyz.")
            proof = response.headers.get("X-PetCare-Demo-Database", "")
            if not hmac.compare_digest(proof, demo_database_signature(settings)):
                raise DemoNotReady(
                    "Web đang dùng database/cấu hình khác hoặc code cũ. Khởi động lại đúng server trước demo."
                )
    except (URLError, OSError, ValueError) as exc:
        raise DemoNotReady(
            "Web chưa sẵn sàng. Chạy python run.py ở terminal khác rồi thử lại."
        ) from exc
    return url


def prepare(settings=Config):
    if settings.APP_ENV == "production" or not settings.DB_NAME.endswith(
        ("_dev", "_test")
    ):
        raise DemoNotReady(
            "Chỉ chuẩn bị demo trên môi trường local với database _dev hoặc _test."
        )
    if not settings.SECRET_KEY_CONFIGURED:
        raise DemoNotReady(
            "Cần SECRET_KEY cố định trong .env để giữ phiên và xác nhận đúng server demo."
        )
    if settings.MEDIA_STORAGE_BACKEND != "local":
        raise DemoNotReady(
            "Preflight offline cần ảnh local; kiểm tra cấu hình MEDIA_STORAGE_BACKEND."
        )
    config = mysql_config(settings)
    config.update(connection_timeout=1)
    connection = mysql.connector.connect(**config)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute("SET time_zone = '+00:00'")
            cursor.execute("SET SESSION innodb_lock_wait_timeout = 1")
            if not schema_contract_is_ready(cursor):
                raise DemoNotReady(
                    "Schema chưa sẵn sàng. Chạy initialize trước buổi demo."
                )
            tenants = _fetch(
                cursor,
                "SELECT id, timezone, default_currency FROM tenants WHERE slug = 'main' AND status = 'active'",
            )
            if not tenants:
                raise DemoNotReady(
                    "Thiếu cửa hàng main. Khởi tạo và seed database demo trước."
                )
            tenant_id, zone, currency = tenants[0]
            actors = _fetch(
                cursor,
                "SELECT u.username, tu.role FROM users u JOIN tenant_users tu ON tu.user_id = u.id "
                "WHERE tu.tenant_id = %s AND u.active = 1 AND tu.active = 1 "
                "AND u.username IN ('admin', 'staff1')",
                (tenant_id,),
            )
            roles = dict(actors)
            if (
                roles.get("admin") not in {"admin", "owner"}
                or roles.get("staff1") != "staff"
            ):
                raise DemoNotReady(
                    "Cần admin và staff1 đang hoạt động đúng quyền; không tự đặt lại mật khẩu/quyền."
                )
            products = _fetch(
                cursor,
                "SELECT code, unit_price, stock_qty FROM products WHERE tenant_id = %s "
                "AND active = 1 AND code IN ('FOOD-001', 'ACC-001')",
                (tenant_id,),
            )
            products = {code: (price, stock) for code, price, stock in products}
            if any(
                code not in products or products[code][1] < qty
                for code, qty in (("FOOD-001", 2), ("ACC-001", 1))
            ):
                raise DemoNotReady(
                    "Đơn mẫu cần FOOD-001 còn ít nhất 2 và ACC-001 còn ít nhất 1. Kiểm tra/nhập kho qua UI."
                )
            pets = _fetch(
                cursor,
                "SELECT code, name, sale_price FROM pets WHERE tenant_id = %s "
                "AND sale_status = 'available' AND photo_filename IS NOT NULL "
                "ORDER BY (code = 'PET-001') DESC, id LIMIT 1",
                (tenant_id,),
            )
            if not pets:
                raise DemoNotReady(
                    "Cần ít nhất một thú cưng có ảnh đang bán; không đưa thú đã bán trở lại kho."
                )
            photo_count = 0
            for kind, sql in (
                (
                    "pets",
                    "SELECT photo_filename FROM pets WHERE tenant_id = %s AND photo_filename IS NOT NULL",
                ),
                (
                    "products",
                    "SELECT photo_filename FROM products WHERE tenant_id = %s AND photo_filename IS NOT NULL",
                ),
            ):
                storage = get_media_storage(settings, kind)
                for (filename,) in _fetch(cursor, sql, (tenant_id,)):
                    try:
                        with storage.open(filename) as image:
                            valid = image.read(3) == b"\xff\xd8\xff"
                    except (OSError, ValueError) as exc:
                        raise DemoNotReady(
                            "Có ảnh hồ sơ bị thiếu/không đọc được. Chạy seed để bù ảnh mẫu hoặc sửa ảnh trước demo."
                        ) from exc
                    if not valid:
                        raise DemoNotReady(
                            "Có ảnh hồ sơ không có header JPEG hợp lệ; kiểm tra ảnh trước demo."
                        )
                    photo_count += 1
            url = _web_ready(settings)
            notes = [
                f"[DEMO] {marker} · dữ liệu giao dịch mẫu" for marker, *_ in DEMO_SALES
            ]
            # Seven fixed seed markers, with every value bound as a parameter.
            rows = _fetch(
                cursor,
                "SELECT id, note, status FROM invoices WHERE tenant_id = %s "
                "AND note IN (%s,%s,%s,%s,%s,%s,%s) FOR UPDATE",
                (tenant_id, *notes),
            )
            by_note = {}
            for invoice_id, note, status in rows:
                if note in by_note:
                    raise DemoNotReady(
                        "Trùng marker hóa đơn mẫu. Kiểm tra dữ liệu demo trước khi tiếp tục."
                    )
                by_note[note] = (invoice_id, status)
            if any(
                note not in by_note or by_note[note][1] not in {"paid", "cancelled"}
                for note in notes
            ):
                raise DemoNotReady(
                    "Thiếu hoặc chưa thanh toán hóa đơn mẫu. Chạy seed đầy đủ trước; preflight không tự thanh toán."
                )
            today_notes = [
                notes[i] for i, sale in enumerate(DEMO_SALES) if sale[1] == 0
            ]
            if not any(by_note[note][1] == "paid" for note in today_notes):
                raise DemoNotReady(
                    "Giao dịch mẫu hôm nay đã hủy; dùng database demo riêng có bộ seed đầy đủ."
                )
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            refreshed, skipped = 0, 0
            for note, sale in zip(notes, DEMO_SALES):
                invoice_id, status = by_note[note]
                if status == "cancelled":
                    skipped += 1
                    continue
                paid_at = now - timedelta(days=sale[1])
                cursor.execute(
                    "UPDATE invoices SET created_at = %s, paid_at = %s "
                    "WHERE tenant_id = %s AND id = %s AND note = %s AND status = 'paid'",
                    (paid_at, paid_at, tenant_id, invoice_id, note),
                )
                cursor.execute(
                    "UPDATE stock_movements SET created_at = %s "
                    "WHERE tenant_id = %s AND invoice_id = %s",
                    (paid_at, tenant_id, invoice_id),
                )
                refreshed += 1
            connection.commit()
            code, name, price = pets[0]
            return {
                "ok": True,
                "database": settings.DB_NAME,
                "today": tenant_today(zone).isoformat(),
                "url": url,
                "currency_code": currency,
                "refreshed_invoices": refreshed,
                "skipped_cancelled": skipped,
                "photo_files_checked": photo_count,
                "pet": {"code": code, "name": name, "price": str(price)},
                "expected_total": str(
                    Decimal(products["FOOD-001"][0]) * 2
                    + Decimal(products["ACC-001"][0])
                    + Decimal(price)
                ),
                "ai": (
                    "optional-provider-with-local-fallback"
                    if settings.AI_API_BASE_URL and settings.AI_MODEL
                    else "local"
                ),
                "checks": [
                    "mysql",
                    "schema",
                    "admin_staff",
                    "demo_stock",
                    "available_pet",
                    "local_photos",
                    "http_readyz",
                ],
            }
        finally:
            cursor.close()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def _worker():
    try:
        result = prepare()
    except DemoNotReady as exc:
        result = {"ok": False, "error": str(exc)}
    except mysql.connector.Error as exc:
        result = {
            "ok": False,
            "error": f"MySQL chưa sẵn sàng (mã {getattr(exc, 'errno', None)}). Kiểm tra Docker/MySQL và .env.",
        }
    except Exception:
        result = {
            "ok": False,
            "error": "Chưa xác nhận được môi trường demo. Kiểm tra cấu hình và chạy lại.",
        }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


def main(argv=None, started=None):
    started = monotonic() if started is None else started
    parser = argparse.ArgumentParser(
        description="Kiểm tra demo local và làm mới đúng hóa đơn mẫu đã thanh toán."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Xuất kết quả JSON và exit code cho automation.",
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        return _worker()
    remaining = BUDGET_SECONDS - (monotonic() - started)
    try:
        if remaining <= 0:
            raise subprocess.TimeoutExpired("prepare-demo", BUDGET_SECONDS)
        # Trusted interpreter and fixed module arguments, with no shell.
        run = subprocess.run(  # nosec B603
            [sys.executable, "-B", "-m", "petcare.prepare_demo", "--worker"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=remaining,
            check=False,
        )
        result = json.loads(run.stdout)
        if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
            raise ValueError("Invalid worker result")
    except subprocess.TimeoutExpired:
        result = {
            "ok": False,
            "error": "Đã hết ngân sách 5 giây; chưa xác nhận sẵn sàng. Kiểm tra MySQL/web rồi chạy lại; không reset dữ liệu.",
        }
    except (OSError, ValueError):
        result = {
            "ok": False,
            "error": "Không chạy được preflight. Kiểm tra venv/.env và chạy lại.",
        }
    result["duration_seconds"] = round(monotonic() - started, 3)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    elif result["ok"]:
        print(
            f"SẴN SÀNG ({result['duration_seconds']:.2f}s) · {result['url']} · ngày {result['today']}"
        )
        print(
            f"MySQL/schema/web/quyền/ảnh/tồn: đạt. Làm mới {result['refreshed_invoices']} hóa đơn mẫu; bỏ qua {result['skipped_cancelled']} hóa đơn đã hủy."
        )
        print(
            f"Đơn demo: 2 FOOD-001 + 1 ACC-001 + 1 {result['pet']['code']} ({result['pet']['name']}); tổng {format_money(result['expected_total'], result['currency_code'])}."
        )
        print(
            "Giữ nguyên kho, trạng thái thú cưng và mật khẩu. Thời gian là kết quả kiểm tra hiện tại."
        )
    else:
        print(f"CHƯA SẴN SÀNG ({result['duration_seconds']:.2f}s): {result['error']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

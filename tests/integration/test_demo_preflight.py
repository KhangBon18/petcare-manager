"""Exercise the public preflight command against MySQL and a live HTTP server."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Thread
from time import monotonic
import unittest

from werkzeug.serving import make_server
from petcare import create_app
from petcare.config import Config
from petcare.database.connection import get_connection
from petcare.database.initialize import initialize_database
from petcare.database.seed import seed_database
from petcare.repositories.base import fetch_all, fetch_one
from petcare.services import invoice_service

TEST_DB = os.getenv("PETCARE_TEST_DB_NAME", "")


@unittest.skipUnless(
    re.fullmatch(r"[A-Za-z0-9_]+_test", TEST_DB),
    "An isolated _test MySQL database is required.",
)
class DemoPreflightIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_db = Config.DB_NAME
        Config.DB_NAME = TEST_DB
        initialize_database()
        seed_database()
        cls.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "phase-four-preflight-integration-key",
                "AI_API_BASE_URL": "",
                "AI_MODEL": "",
                "AI_API_KEY": "",
            }
        )

    @classmethod
    def tearDownClass(cls):
        Config.DB_NAME = cls.previous_db

    def test_cli_prepares_real_mysql_with_live_readiness_under_five_seconds_and_no_repayment(
        self,
    ):
        server = make_server("127.0.0.1", 0, self.app, threaded=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        invoice_id = None
        with get_connection() as connection:
            tenant = fetch_one(connection, "SELECT id FROM tenants WHERE slug='main'")[
                "id"
            ]
            actor = fetch_one(
                connection, "SELECT id FROM users WHERE username='admin'"
            )["id"]
            customer = fetch_one(
                connection,
                "SELECT id FROM customers WHERE tenant_id=%s ORDER BY id LIMIT 1",
                (tenant,),
            )["id"]
            product = fetch_one(
                connection,
                "SELECT id,stock_qty FROM products WHERE tenant_id=%s AND code='FOOD-005'",
                (tenant,),
            )
        try:
            invoice_id = invoice_service.create_invoice(
                actor,
                {
                    "customer_id": str(customer),
                    "note": "Phase 4 business invoice; not a seed marker",
                },
                [
                    {
                        "item_type": "product",
                        "item_id": str(product["id"]),
                        "quantity": "1",
                    }
                ],
                tenant_id=tenant,
            )
            invoice_service.pay_invoice(actor, invoice_id, tenant_id=tenant)

            def snapshot():
                with get_connection() as connection:
                    return {
                        "products": fetch_all(
                            connection, "SELECT id,stock_qty FROM products ORDER BY id"
                        ),
                        "pets": fetch_all(
                            connection,
                            "SELECT id,sale_status,buyer_id FROM pets ORDER BY id",
                        ),
                        "movements": fetch_one(
                            connection, "SELECT COUNT(*) n FROM stock_movements"
                        )["n"],
                        "business": fetch_one(
                            connection,
                            "SELECT created_at,paid_at,status FROM invoices WHERE id=%s",
                            (invoice_id,),
                        ),
                        "dates": fetch_all(
                            connection,
                            "SELECT id,created_at,paid_at FROM invoices WHERE tenant_id=%s AND note LIKE '[DEMO] DEMO-SALE-%%' ORDER BY id",
                            (tenant,),
                        ),
                    }

            before = snapshot()
            env = dict(
                os.environ,
                DB_NAME=TEST_DB,
                APP_ENV="test",
                APP_PORT=str(server.server_port),
                SECRET_KEY=self.app.config["SECRET_KEY"],
                PET_IMAGE_DIR=self.app.config["PET_IMAGE_DIR"],
                PRODUCT_IMAGE_DIR=self.app.config["PRODUCT_IMAGE_DIR"],
                MEDIA_STORAGE_BACKEND="local",
            )
            for _ in range(2):
                started = monotonic()
                run = subprocess.run(
                    [sys.executable, "-B", "run.py", "prepare-demo", "--json"],
                    cwd=Path(__file__).resolve().parents[2],
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=7,
                )
                duration = monotonic() - started
                self.assertEqual(run.returncode, 0, run.stdout + " " + run.stderr)
                result = json.loads(run.stdout)
                self.assertTrue(result["ok"])
                self.assertLess(duration, 5)
                self.assertEqual(result["refreshed_invoices"], 7)
                self.assertIn("http_readyz", result["checks"])
                self.assertEqual(result["database"], TEST_DB)
                self.assertEqual(result["pet"]["code"], "PET-001")
            after = snapshot()
            for key in ["products", "pets", "movements", "business"]:
                self.assertEqual(before[key], after[key])
            wrong_env = {**env, "SECRET_KEY": "different-server-configuration"}
            run = subprocess.run(
                [sys.executable, "-B", "run.py", "prepare-demo", "--json"],
                cwd=Path(__file__).resolve().parents[2],
                env=wrong_env,
                text=True,
                capture_output=True,
                timeout=7,
            )
            self.assertNotEqual(run.returncode, 0)
            self.assertFalse(json.loads(run.stdout)["ok"])
            self.assertEqual(after["dates"], snapshot()["dates"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            if invoice_id:
                with get_connection() as connection:
                    cursor = connection.cursor()
                    cursor.execute(
                        "DELETE FROM audit_events WHERE entity_type='invoice' AND entity_id=%s",
                        (invoice_id,),
                    )
                    cursor.execute(
                        "DELETE FROM stock_movements WHERE invoice_id=%s", (invoice_id,)
                    )
                    cursor.execute(
                        "DELETE FROM invoice_items WHERE invoice_id=%s", (invoice_id,)
                    )
                    cursor.execute("DELETE FROM invoices WHERE id=%s", (invoice_id,))
                    cursor.execute(
                        "UPDATE products SET stock_qty=%s WHERE id=%s",
                        (product["stock_qty"], product["id"]),
                    )
                    connection.commit()
                    cursor.close()

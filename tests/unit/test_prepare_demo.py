from contextlib import redirect_stdout
from decimal import Decimal
from io import BytesIO, StringIO
import json
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from petcare import prepare_demo


class PrepareDemoTests(unittest.TestCase):
    def settings(self, **changes):
        values = dict(
            APP_ENV="test",
            DB_NAME="demo_test",
            MEDIA_STORAGE_BACKEND="local",
            SECRET_KEY_CONFIGURED=True,
            SECRET_KEY="preflight-unit-key",
            DB_HOST="127.0.0.1",
            DB_PORT=3306,
            APP_PORT=5056,
            AI_API_BASE_URL="",
            AI_MODEL="",
        )
        values.update(changes)
        return SimpleNamespace(**values)

    def fixture(self, statuses=None):
        notes = [
            f"[DEMO] {sale[0]} · dữ liệu giao dịch mẫu"
            for sale in prepare_demo.DEMO_SALES
        ]
        invoices = [
            (i + 1, note, (statuses or {}).get(i, "paid"))
            for i, note in enumerate(notes)
        ]
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchall.side_effect = [
            [(1, "Asia/Ho_Chi_Minh", "VND")],
            [("admin", "owner"), ("staff1", "staff")],
            [("FOOD-001", Decimal(100000), 10), ("ACC-001", Decimal(50000), 5)],
            [("PET-001", "Miu", Decimal(2000000))],
            [("photo.jpg",)],
            [],
            invoices,
        ]
        storage = MagicMock()
        storage.open.side_effect = lambda _: BytesIO(b"\xff\xd8\xfftest")
        return connection, cursor, storage

    def run_prepare(self, connection, storage, **extra):
        with patch.object(prepare_demo, "mysql_config", return_value={}), patch.object(
            prepare_demo.mysql.connector, "connect", return_value=connection
        ), patch.object(
            prepare_demo, "schema_contract_is_ready", return_value=True
        ), patch.object(
            prepare_demo, "get_media_storage", return_value=storage
        ), patch.object(
            prepare_demo,
            "_web_ready",
            **(extra or {"return_value": "http://127.0.0.1:5056"}),
        ):
            return prepare_demo.prepare(self.settings())

    def test_refresh_only_exact_paid_markers_and_preserve_business_state(self):
        connection, cursor, storage = self.fixture({6: "cancelled"})
        result = self.run_prepare(connection, storage)
        self.assertTrue(result["ok"])
        self.assertEqual(result["refreshed_invoices"], 6)
        self.assertEqual(result["skipped_cancelled"], 1)
        self.assertEqual(Decimal(result["expected_total"]), 2250000)
        writes = [
            call.args
            for call in cursor.execute.call_args_list
            if call.args[0].startswith("UPDATE")
        ]
        self.assertEqual(len(writes), 12)
        self.assertTrue(
            all(
                sql.startswith(
                    (
                        "UPDATE invoices SET created_at",
                        "UPDATE stock_movements SET created_at",
                    )
                )
                for sql, _ in writes
            )
        )
        for sql, params in writes:
            if sql.startswith("UPDATE invoices"):
                self.assertIn("AND note = %s AND status = 'paid'", sql)
                self.assertTrue(params[-1].startswith("[DEMO] DEMO-SALE-"))
        connection.commit.assert_called_once()
        connection.rollback.assert_not_called()

    def test_missing_or_unpaid_seed_fails_before_any_update(self):
        for status in ["unpaid", "cancelled"]:
            with self.subTest(status=status):
                connection, cursor, storage = self.fixture({0: status})
                with self.assertRaises(prepare_demo.DemoNotReady):
                    self.run_prepare(connection, storage)
                self.assertFalse(
                    any(
                        call.args[0].startswith("UPDATE")
                        for call in cursor.execute.call_args_list
                    )
                )
                connection.rollback.assert_called_once()
                connection.commit.assert_not_called()

    def test_http_failure_rolls_back_and_does_not_change_dates(self):
        connection, cursor, storage = self.fixture()
        with self.assertRaises(prepare_demo.DemoNotReady):
            self.run_prepare(
                connection,
                storage,
                side_effect=prepare_demo.DemoNotReady("web unavailable"),
            )
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()
        self.assertFalse(
            any(
                call.args[0].startswith("UPDATE")
                for call in cursor.execute.call_args_list
            )
        )

    def test_failure_between_invoice_and_movement_updates_rolls_back(self):
        connection, cursor, storage = self.fixture()

        def execute(sql, *args):
            if sql.startswith("UPDATE stock_movements"):
                raise prepare_demo.mysql.connector.Error("test failure")

        cursor.execute.side_effect = execute
        with self.assertRaises(prepare_demo.mysql.connector.Error):
            self.run_prepare(connection, storage)
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()
        connection.close.assert_called_once()

    def test_production_real_database_unstable_secret_and_remote_media_are_rejected_before_connect(
        self,
    ):
        for changes in [
            {"APP_ENV": "production"},
            {"DB_NAME": "real_shop"},
            {"SECRET_KEY_CONFIGURED": False},
            {"MEDIA_STORAGE_BACKEND": "s3"},
        ]:
            with self.subTest(changes=changes), patch.object(
                prepare_demo.mysql.connector, "connect"
            ) as connect:
                with self.assertRaises(prepare_demo.DemoNotReady):
                    prepare_demo.prepare(self.settings(**changes))
                connect.assert_not_called()

    def test_http_checks_database_signature_and_rejects_wrong_server(self):
        settings = self.settings()
        for proof, valid in [
            (prepare_demo.demo_database_signature(settings), True),
            ("wrong-database", False),
        ]:
            response = MagicMock()
            response.status = 200
            response.read.return_value = b'{"status":"ready"}'
            response.headers = {"X-PetCare-Demo-Database": proof}
            opener = MagicMock()
            opener.open.return_value.__enter__.return_value = response
            with self.subTest(valid=valid), patch.object(
                prepare_demo, "build_opener", return_value=opener
            ):
                if valid:
                    self.assertEqual(
                        prepare_demo._web_ready(settings), "http://127.0.0.1:5056"
                    )
                else:
                    with self.assertRaises(prepare_demo.DemoNotReady):
                        prepare_demo._web_ready(settings)
                self.assertEqual(opener.open.call_args.kwargs["timeout"], 1)

    def test_parent_timeout_is_bounded_and_never_claims_ready(self):
        output = StringIO()
        with patch.object(
            prepare_demo.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("preflight", 4.7),
        ) as run, redirect_stdout(output):
            code = prepare_demo.main(["--json"])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(result["ok"])
        self.assertLessEqual(run.call_args.kwargs["timeout"], 4.7)
        self.assertIn("5 giây", result["error"])

    def test_worker_errors_are_sanitized_without_database_credentials(self):
        output = StringIO()
        error = prepare_demo.mysql.connector.Error("password=do-not-print", errno=2003)
        with patch.object(prepare_demo, "prepare", side_effect=error), redirect_stdout(
            output
        ):
            code = prepare_demo._worker()
        result = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(result["ok"])
        self.assertIn("2003", result["error"])
        self.assertNotIn("do-not-print", output.getvalue())

    def test_broken_worker_output_returns_failure_without_leaking_stderr(self):
        output = StringIO()
        result = subprocess.CompletedProcess(
            [], 1, stdout="not JSON", stderr="secret error detail"
        )
        with patch.object(
            prepare_demo.subprocess, "run", return_value=result
        ), redirect_stdout(output):
            code = prepare_demo.main(["--json"])
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output.getvalue())["ok"])
        self.assertNotIn("secret error", output.getvalue())

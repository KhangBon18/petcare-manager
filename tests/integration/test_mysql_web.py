import os
import re
import hashlib
import hmac
import unittest
import json
import csv
import stat
import tempfile
from threading import Event, Thread, current_thread
import zipfile
from pathlib import Path
from io import BytesIO, StringIO
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4
from urllib.parse import parse_qs, urlsplit

from PIL import Image
from cryptography.fernet import Fernet
from mysql.connector import IntegrityError
from flask import g
from werkzeug.datastructures import FileStorage

from petcare import create_app
from petcare.config import Config
from petcare.database.connection import get_connection
from petcare.database.connection import transaction
from petcare.database.initialize import initialize_database
from petcare.database.create_store import create_store
from petcare.database.export_tenant import (
    decrypt_tenant_export,
    export_tenant,
    verify_encrypted_tenant_export,
)
from petcare.database.seed import CUSTOMERS, DEMO_SALES, PETS, PRODUCTS, seed_database
from petcare.repositories.base import fetch_all, fetch_one
from petcare.repositories import pet_repo, product_repo, worker_heartbeat_repo
from petcare.services import auth_service, invoice_service, pet_service, product_service, tenant_owner_transfer_service
from petcare.services.exceptions import ForbiddenError, ValidationError
from petcare.services.mail_service import MailDeliveryError, enqueue_text_email
from petcare.services.mail_outbox_worker import dispatch_one
from petcare.services.tenant_export_worker import process_one as process_tenant_export_one
from petcare.services.tenant_signup_cleanup import cleanup_expired_public_signups
from petcare.vision.reindex_pet_descriptors import reindex_pet_descriptors


TEST_DB = os.getenv("PETCARE_TEST_DB_NAME", "")


@unittest.skipUnless(
    re.fullmatch(r"[A-Za-z0-9_]+_test", TEST_DB),
    "Set PETCARE_TEST_DB_NAME to an isolated MySQL database ending in _test.",
)
class MySQLWebIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_db_name = Config.DB_NAME
        Config.DB_NAME = TEST_DB
        initialize_database()
        seed_database()
        cls.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "mysql-web-tests-only-secret",
            "WTF_CSRF_ENABLED": True,
            "TENANT_INVITATION_RATE_LIMIT_PER_MINUTE": 1000,
            "PUBLIC_SIGNUP_EMAIL_RATE_LIMIT_PER_MINUTE": 1000,
            "PUBLIC_SIGNUP_IP_RATE_LIMIT_PER_MINUTE": 1000,
            "TENANT_OWNER_TRANSFER_RATE_LIMIT_PER_MINUTE": 1000,
            "AI_API_BASE_URL": "",
            "AI_API_KEY": "",
            "AI_MODEL": "",
        })

    @classmethod
    def tearDownClass(cls):
        Config.DB_NAME = cls.previous_db_name

    def _login(self, username, password, store_slug="main"):
        client = self.app.test_client()
        response = client.get("/login")
        html = response.get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html)
        self.assertIsNotNone(token)
        response = client.post(
            "/login",
            data={
                "csrf_token": token.group(1),
                "store_slug": store_slug,
                "username": username,
                "password": password,
            },
        )
        self.assertEqual(response.status_code, 302)
        return client

    def _csrf_token(self, client, path):
        response = client.get(path)
        self.assertEqual(response.status_code, 200)
        match = re.search(
            r'name="csrf_token" value="([^"]+)"',
            response.get_data(as_text=True),
        )
        self.assertIsNotNone(match)
        return match.group(1)

    def _create_invitation(self, client, role="staff", email=None):
        email = email or f"invite-{uuid4().hex}@example.test"
        token = self._csrf_token(client, "/users/")
        mail_config = {key: self.app.config.get(key) for key in ("MAIL_HOST", "MAIL_FROM")}
        try:
            self.app.config.update(MAIL_HOST="", MAIL_FROM="")
            response = client.post(
                "/users/invitations",
                data={"csrf_token": token, "role": role, "email": email},
                follow_redirects=True,
            )
        finally:
            self.app.config.update(mail_config)
        self.assertEqual(response.status_code, 200)
        match = re.search(
            r"(https?://[^/]+)?(/users/invitations/accept\?token=[A-Za-z0-9_-]{43})",
            response.get_data(as_text=True),
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), self.app.config["PUBLIC_BASE_URL"])
        return match.group(2)

    def test_admin_and_staff_access_real_routes(self):
        admin = self._login("admin", "Admin@123")
        response = admin.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn("TỔNG QUAN CỬA HÀNG", response.get_data(as_text=True))
        self.assertEqual(admin.get("/users/").status_code, 200)
        self.assertEqual(admin.get("/activity/").status_code, 200)
        self.assertEqual(admin.get("/store/settings").status_code, 200)

        staff = self._login("staff1", "Staff@123")
        self.assertEqual(staff.get("/dashboard").status_code, 200)
        self.assertEqual(staff.get("/users/").status_code, 403)
        self.assertEqual(staff.get("/activity/").status_code, 403)
        self.assertEqual(staff.get("/store/settings").status_code, 403)

    def test_account_language_preference_survives_a_new_browser_session(self):
        client = self._login("admin", "Admin@123")
        with get_connection() as connection:
            user = fetch_one(
                connection,
                "SELECT id, preferred_locale FROM users WHERE username = 'admin'",
            )
        try:
            response = client.post(
                "/language",
                data={
                    "csrf_token": self._csrf_token(client, "/dashboard"),
                    "locale": "en",
                    "next": "/dashboard",
                },
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("Dashboard", response.get_data(as_text=True))

            new_client = self._login("admin", "Admin@123")
            new_session_dashboard = new_client.get("/dashboard").get_data(as_text=True)
            self.assertIn("Dashboard", new_session_dashboard)
            with get_connection() as connection:
                preference = fetch_one(
                    connection,
                    "SELECT preferred_locale FROM users WHERE id = %s",
                    (user["id"],),
                )
            self.assertEqual(preference["preferred_locale"], "en")
        finally:
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE users SET preferred_locale = %s WHERE id = %s",
                        (user["preferred_locale"], user["id"]),
                    )
                    connection.commit()
                finally:
                    cursor.close()

    def test_additive_migration_adds_locale_preference_to_legacy_users(self):
        with get_connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("ALTER TABLE users DROP CHECK chk_users_preferred_locale")
                cursor.execute("ALTER TABLE users DROP COLUMN preferred_locale")
                connection.commit()
            finally:
                cursor.close()

        initialize_database()

        with get_connection() as connection:
            column = fetch_one(
                connection,
                "SELECT COUNT(*) total FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'users' "
                "AND column_name = 'preferred_locale'",
            )
            constraint = fetch_one(
                connection,
                "SELECT COUNT(*) total FROM information_schema.table_constraints "
                "WHERE constraint_schema = DATABASE() AND table_name = 'users' "
                "AND constraint_name = 'chk_users_preferred_locale'",
            )
        self.assertEqual(column["total"], 1)
        self.assertEqual(constraint["total"], 1)

    def test_store_settings_update_tenant_name_timezone_and_audit_atomically(self):
        suffix = uuid4().hex[:12]
        slug = "settings-" + suffix
        username = "settings_" + suffix
        password = "Settings@123"
        tenant_id, user_id = create_store(
            slug, "Settings " + suffix, username, "Settings Owner", password
        )
        client = self._login(username, password, slug)
        try:
            page = client.get("/store/settings")
            self.assertEqual(page.status_code, 200)
            self.assertIn("Múi giờ IANA", page.get_data(as_text=True))

            response = client.post(
                "/store/settings",
                data={
                    "csrf_token": self._csrf_token(client, "/store/settings"),
                    "name": "Updated Settings Store",
                    "timezone": "America/New_York",
                },
            )
            self.assertEqual(response.status_code, 302)
            updated_page = client.get("/store/settings")
            self.assertIn("Updated Settings Store", updated_page.get_data(as_text=True))
            with get_connection() as connection:
                tenant = fetch_one(
                    connection,
                    "SELECT name, slug, default_currency, timezone FROM tenants WHERE id = %s",
                    (tenant_id,),
                )
                event = fetch_one(
                    connection,
                    "SELECT event_type, entity_id, details FROM audit_events "
                    "WHERE tenant_id = %s AND actor_user_id = %s "
                    "AND event_type = 'tenant.settings_updated' ORDER BY id DESC LIMIT 1",
                    (tenant_id, user_id),
                )
            self.assertEqual(tenant, {
                "name": "Updated Settings Store",
                "slug": slug,
                "default_currency": "VND",
                "timezone": "America/New_York",
            })
            self.assertEqual(event["entity_id"], tenant_id)
            details = event["details"]
            if isinstance(details, str):
                details = json.loads(details)
            self.assertEqual(details["changed_fields"], ["name", "timezone"])

            response = client.post(
                "/store/settings",
                data={
                    "csrf_token": self._csrf_token(client, "/store/settings"),
                    "name": "Should Not Save",
                    "timezone": "Not/A-Timezone",
                },
            )
            self.assertEqual(response.status_code, 302)
            with get_connection() as connection:
                unchanged = fetch_one(
                    connection,
                    "SELECT name, timezone FROM tenants WHERE id = %s",
                    (tenant_id,),
                )
            self.assertEqual(unchanged, {
                "name": "Updated Settings Store",
                "timezone": "America/New_York",
            })
        finally:
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute("DELETE FROM audit_events WHERE tenant_id = %s", (tenant_id,))
                    cursor.execute("DELETE FROM tenant_users WHERE tenant_id = %s", (tenant_id,))
                    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                    cursor.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
                    connection.commit()
                finally:
                    cursor.close()

    def test_store_owner_is_visible_and_cannot_be_demoted_or_locked(self):
        client = self._login("admin", "Admin@123")
        page = client.get("/users/")
        self.assertIn("Chủ cửa hàng", page.get_data(as_text=True))
        self.assertIn("Không thể đổi vai trò hoặc khóa tại đây", page.get_data(as_text=True))
        with get_connection() as connection:
            owner = fetch_one(
                connection,
                "SELECT u.id, tu.role, tu.active FROM users u "
                "JOIN tenant_users tu ON tu.user_id = u.id "
                "JOIN tenants t ON t.id = tu.tenant_id "
                "WHERE u.username = 'admin' AND t.slug = 'main'",
            )

        response = client.post(
            f"/users/{owner['id']}/update",
            data={
                "csrf_token": self._csrf_token(client, "/users/"),
                "full_name": "Admin",
                "role": "staff",
                "active": "0",
                "password": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("Không thể đổi vai trò hoặc khóa chủ cửa hàng", client.get("/users/").get_data(as_text=True))
        with get_connection() as connection:
            unchanged = fetch_one(
                connection,
                "SELECT tu.role, tu.active FROM tenant_users tu "
                "JOIN tenants t ON t.id = tu.tenant_id "
                "WHERE tu.user_id = %s AND t.slug = 'main'",
                (owner["id"],),
            )
        self.assertEqual(unchanged, {"role": "owner", "active": 1})

    def test_owner_transfer_requires_both_accounts_to_reauthenticate_and_accept(self):
        owner = self._login("admin", "Admin@123")
        suffix = uuid4().hex[:10]
        target_username = "handoff_" + suffix
        target_password = "Handoff@123"
        invite_email = f"handoff-{suffix}@example.test"
        invitation_path = self._create_invitation(owner, "admin", invite_email)
        invite_token = parse_qs(urlsplit(invitation_path).query)["token"][0]

        target = self.app.test_client()
        invitation_page = target.get(invitation_path)
        invite_csrf = re.search(
            r'name="csrf_token" value="([^"]+)"', invitation_page.get_data(as_text=True)
        ).group(1)
        accepted_invitation = target.post(
            "/users/invitations/accept",
            data={
                "csrf_token": invite_csrf,
                "token": invite_token,
                "username": target_username,
                "password": target_password,
                "full_name": "Handoff Admin",
            },
        )
        self.assertEqual(accepted_invitation.status_code, 302)
        target_user = self._login(target_username, target_password)

        owner_page = owner.get("/users/ownership")
        self.assertEqual(owner_page.status_code, 200)
        self.assertIn(target_username, owner_page.get_data(as_text=True))
        owner_csrf = self._csrf_token(owner, "/users/ownership")
        wrong_password = owner.post(
            "/users/ownership",
            data={
                "csrf_token": owner_csrf,
                "target_user_id": "0",
                "current_password": "incorrect password",
            },
            follow_redirects=True,
        )
        self.assertIn("Chọn quản trị viên", wrong_password.get_data(as_text=True))

        with get_connection() as connection:
            target_record = fetch_one(
                connection,
                "SELECT id FROM users WHERE username = %s",
                (target_username,),
            )
            tenant = fetch_one(connection, "SELECT id FROM tenants WHERE slug = 'main'")
            owner_record = fetch_one(
                connection,
                "SELECT tu.user_id FROM tenant_users tu JOIN users u ON u.id = tu.user_id "
                "WHERE tu.tenant_id = %s AND tu.role = 'owner' AND tu.active = 1 "
                "AND u.username = 'admin'",
                (tenant["id"],),
            )
        target_user_id = target_record["id"]
        owner_user_id = owner_record["user_id"]

        config_mail = {key: self.app.config.get(key) for key in ("MAIL_HOST", "MAIL_FROM")}
        try:
            self.app.config.update(MAIL_HOST="", MAIL_FROM="")
            owner_csrf = self._csrf_token(owner, "/users/ownership")
            second_owner = self._login("admin", "Admin@123")
            second_owner_csrf = self._csrf_token(second_owner, "/users/ownership")
            first_holds_tenant_lock = Event()
            second_waiting_for_lock = Event()
            release_first = Event()
            race_responses = {}
            race_errors = []
            original_require_active_tenant = tenant_owner_transfer_service._require_active_tenant

            def pause_first_handoff(connection, tenant_id):
                if current_thread().name == "owner-transfer-first":
                    tenant_result = original_require_active_tenant(connection, tenant_id)
                    first_holds_tenant_lock.set()
                    if not release_first.wait(10):
                        raise TimeoutError("Timed out waiting to release the first owner handoff")
                    return tenant_result
                if current_thread().name == "owner-transfer-second":
                    second_waiting_for_lock.set()
                return original_require_active_tenant(connection, tenant_id)

            def submit_handoff(name, client, csrf_token):
                try:
                    race_responses[name] = client.post(
                        "/users/ownership",
                        data={
                            "csrf_token": csrf_token,
                            "target_user_id": str(target_user_id),
                            "current_password": "Admin@123",
                        },
                        follow_redirects=True,
                    )
                except Exception as exc:
                    race_errors.append(exc)

            with patch.object(
                tenant_owner_transfer_service,
                "_require_active_tenant",
                side_effect=pause_first_handoff,
            ):
                first_thread = Thread(
                    target=submit_handoff,
                    name="owner-transfer-first",
                    args=("first", owner, owner_csrf),
                )
                second_thread = Thread(
                    target=submit_handoff,
                    name="owner-transfer-second",
                    args=("second", second_owner, second_owner_csrf),
                )
                first_thread.start()
                self.assertTrue(first_holds_tenant_lock.wait(5))
                second_thread.start()
                self.assertTrue(second_waiting_for_lock.wait(5))
                release_first.set()
                first_thread.join(15)
                second_thread.join(15)
            self.assertFalse(first_thread.is_alive())
            self.assertFalse(second_thread.is_alive())
            self.assertEqual(race_errors, [])
            with get_connection() as connection:
                open_transfers = fetch_one(
                    connection,
                    "SELECT id, COUNT(*) OVER () total FROM tenant_owner_transfers "
                    "WHERE tenant_id = %s AND accepted_at IS NULL AND cancelled_at IS NULL "
                    "AND expires_at > CURRENT_TIMESTAMP ORDER BY id DESC LIMIT 1",
                    (tenant["id"],),
                )
            self.assertIsNotNone(open_transfers)
            self.assertEqual(open_transfers["total"], 1)
            response_text = "\n".join(
                response.get_data(as_text=True) for response in race_responses.values()
            )
            self.assertIn("Đã tạo yêu cầu", response_text)
            self.assertIn("đang chờ xử lý", response_text)
            pending_csrf = self._csrf_token(owner, "/users/ownership")
            cancelled_race = owner.post(
                f"/users/ownership/{open_transfers['id']}/cancel",
                data={"csrf_token": pending_csrf, "current_password": "Admin@123"},
                follow_redirects=True,
            )
            self.assertIn("Đã thu hồi yêu cầu", cancelled_race.get_data(as_text=True))

            bad_reauth = owner.post(
                "/users/ownership",
                data={
                    "csrf_token": owner_csrf,
                    "target_user_id": str(target_user_id),
                    "current_password": "incorrect password",
                },
                follow_redirects=True,
            )
            self.assertIn("Mật khẩu hiện tại không chính xác", bad_reauth.get_data(as_text=True))
            with get_connection() as connection:
                no_transfer = fetch_one(
                    connection,
                    "SELECT COUNT(*) total FROM tenant_owner_transfers WHERE tenant_id = %s "
                    "AND accepted_at IS NULL AND cancelled_at IS NULL "
                    "AND expires_at > CURRENT_TIMESTAMP",
                    (tenant["id"],),
                )
            self.assertEqual(no_transfer["total"], 0)

            owner_csrf = self._csrf_token(owner, "/users/ownership")
            started = owner.post(
                "/users/ownership",
                data={
                    "csrf_token": owner_csrf,
                    "target_user_id": str(target_user_id),
                    "current_password": "Admin@123",
                },
                follow_redirects=True,
            )
            self.assertIn("Đã tạo yêu cầu", started.get_data(as_text=True))
            with get_connection() as connection:
                cancelled_transfer = fetch_one(
                    connection,
                    "SELECT id, expires_at FROM tenant_owner_transfers "
                    "WHERE tenant_id = %s AND requested_by = %s AND target_user_id = %s "
                    "AND accepted_at IS NULL AND cancelled_at IS NULL "
                    "AND expires_at > CURRENT_TIMESTAMP ORDER BY id DESC LIMIT 1",
                    (tenant["id"], owner_user_id, target_user_id),
                )
            self.assertIsNotNone(cancelled_transfer)
            cancel_csrf = self._csrf_token(owner, "/users/ownership")
            bad_cancel = owner.post(
                f"/users/ownership/{cancelled_transfer['id']}/cancel",
                data={"csrf_token": cancel_csrf, "current_password": "incorrect password"},
                follow_redirects=True,
            )
            self.assertIn("Mật khẩu hiện tại không chính xác", bad_cancel.get_data(as_text=True))
            cancel_csrf = self._csrf_token(owner, "/users/ownership")
            cancelled = owner.post(
                f"/users/ownership/{cancelled_transfer['id']}/cancel",
                data={"csrf_token": cancel_csrf, "current_password": "Admin@123"},
                follow_redirects=True,
            )
            self.assertIn("Đã thu hồi yêu cầu bàn giao", cancelled.get_data(as_text=True))
            with get_connection() as connection:
                cancelled_status = fetch_one(
                    connection,
                    "SELECT cancelled_at FROM tenant_owner_transfers WHERE id = %s",
                    (cancelled_transfer["id"],),
                )
            self.assertIsNotNone(cancelled_status["cancelled_at"])

            owner_csrf = self._csrf_token(owner, "/users/ownership")
            owner.post(
                "/users/ownership",
                data={
                    "csrf_token": owner_csrf,
                    "target_user_id": str(target_user_id),
                    "current_password": "Admin@123",
                },
            )
            with get_connection() as connection:
                expired_transfer = fetch_one(
                    connection,
                    "SELECT id FROM tenant_owner_transfers WHERE tenant_id = %s "
                    "AND requested_by = %s AND target_user_id = %s "
                    "AND accepted_at IS NULL AND cancelled_at IS NULL "
                    "ORDER BY id DESC LIMIT 1",
                    (tenant["id"], owner_user_id, target_user_id),
                )
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE tenant_owner_transfers SET expires_at = DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 1 SECOND) "
                        "WHERE id = %s",
                        (expired_transfer["id"],),
                    )
                    connection.commit()
                finally:
                    cursor.close()
            expired_csrf = self._csrf_token(target_user, "/users/ownership")
            expired_accept = target_user.post(
                f"/users/ownership/{expired_transfer['id']}/accept",
                data={"csrf_token": expired_csrf, "current_password": target_password},
            )
            self.assertEqual(expired_accept.status_code, 404)
            with get_connection() as connection:
                stale_roles = fetch_all(
                    connection,
                    "SELECT user_id, role FROM tenant_users WHERE tenant_id = %s "
                    "AND user_id IN (%s, %s) ORDER BY user_id",
                    (tenant["id"], owner_user_id, target_user_id),
                )
            self.assertEqual(stale_roles, [
                {"user_id": owner_user_id, "role": "owner"},
                {"user_id": target_user_id, "role": "admin"},
            ])

            owner_csrf = self._csrf_token(owner, "/users/ownership")
            owner.post(
                "/users/ownership",
                data={
                    "csrf_token": owner_csrf,
                    "target_user_id": str(target_user_id),
                    "current_password": "Admin@123",
                },
            )
            target_page = target_user.get("/users/ownership")
            self.assertEqual(target_page.status_code, 200)
            self.assertIn("Xác nhận nhận bàn giao", target_page.get_data(as_text=True))
            with get_connection() as connection:
                transfer = fetch_one(
                    connection,
                    "SELECT id, expires_at FROM tenant_owner_transfers "
                    "WHERE tenant_id = %s AND requested_by = %s AND target_user_id = %s "
                    "AND accepted_at IS NULL AND cancelled_at IS NULL "
                    "AND expires_at > CURRENT_TIMESTAMP ORDER BY id DESC LIMIT 1",
                    (tenant["id"], owner_user_id, target_user_id),
                )
            self.assertIsNotNone(transfer)

            target_csrf = self._csrf_token(target_user, "/users/ownership")
            wrong_target_password = target_user.post(
                f"/users/ownership/{transfer['id']}/accept",
                data={"csrf_token": target_csrf, "current_password": "incorrect password"},
                follow_redirects=True,
            )
            self.assertIn("Mật khẩu hiện tại không chính xác", wrong_target_password.get_data(as_text=True))
            with get_connection() as connection:
                still_pending = fetch_one(
                    connection,
                    "SELECT accepted_at FROM tenant_owner_transfers WHERE id = %s",
                    (transfer["id"],),
                )
            self.assertIsNone(still_pending["accepted_at"])

            target_csrf = self._csrf_token(target_user, "/users/ownership")
            accepted = target_user.post(
                f"/users/ownership/{transfer['id']}/accept",
                data={"csrf_token": target_csrf, "current_password": target_password},
                follow_redirects=True,
            )
            self.assertIn("Bạn đã nhận bàn giao", accepted.get_data(as_text=True))
            with get_connection() as connection:
                memberships = fetch_all(
                    connection,
                    "SELECT user_id, role FROM tenant_users WHERE tenant_id = %s "
                    "AND user_id IN (%s, %s) ORDER BY user_id",
                    (tenant["id"], owner_user_id, target_user_id),
                )
                accepted_transfer = fetch_one(
                    connection,
                    "SELECT accepted_at FROM tenant_owner_transfers WHERE id = %s",
                    (transfer["id"],),
                )
                transfer_audit = fetch_all(
                    connection,
                    "SELECT event_type FROM audit_events WHERE tenant_id = %s "
                    "AND entity_type = 'owner_transfer' AND entity_id IN "
                    "(SELECT id FROM tenant_owner_transfers WHERE tenant_id = %s AND target_user_id = %s) "
                    "ORDER BY event_type",
                    (tenant["id"], tenant["id"], target_user_id),
                )
            self.assertEqual(memberships, [
                {"user_id": owner_user_id, "role": "admin"},
                {"user_id": target_user_id, "role": "owner"},
            ])
            self.assertIsNotNone(accepted_transfer["accepted_at"])
            event_types = [event["event_type"] for event in transfer_audit]
            self.assertEqual(event_types.count("membership.owner_transfer_requested"), 4)
            self.assertEqual(event_types.count("membership.owner_transfer_cancelled"), 2)
            self.assertEqual(event_types.count("membership.owner_transferred"), 1)
            self.assertEqual(owner.get("/users/").status_code, 200)
        finally:
            self.app.config.update(config_mail)
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "SELECT id FROM tenant_invitations WHERE tenant_id = %s AND email = %s",
                        (tenant["id"], invite_email),
                    )
                    invitation = cursor.fetchone()
                    invitation_id = invitation[0] if invitation else None
                    cursor.execute(
                        "SELECT id FROM tenant_owner_transfers WHERE tenant_id = %s AND target_user_id = %s",
                        (tenant["id"], target_user_id),
                    )
                    transfer_ids = [row[0] for row in cursor.fetchall()]
                    if invitation_id is not None:
                        cursor.execute(
                            "DELETE FROM audit_events WHERE tenant_id = %s AND "
                            "((entity_type = 'invitation' AND entity_id = %s) OR actor_user_id = %s)",
                            (tenant["id"], invitation_id, target_user_id),
                        )
                    if transfer_ids:
                        marks = ",".join(["%s"] * len(transfer_ids))
                        cursor.execute(
                            f"DELETE FROM audit_events WHERE tenant_id = %s AND entity_type = 'owner_transfer' "
                            f"AND entity_id IN ({marks})",
                            (tenant["id"], *transfer_ids),
                        )
                    cursor.execute(
                        "UPDATE tenant_users SET role = 'owner' WHERE tenant_id = %s AND user_id = %s",
                        (tenant["id"], owner_user_id),
                    )
                    if transfer_ids:
                        marks = ",".join(["%s"] * len(transfer_ids))
                        cursor.execute(
                            f"DELETE FROM tenant_owner_transfers WHERE id IN ({marks})",
                            tuple(transfer_ids),
                        )
                    if invitation_id is not None:
                        cursor.execute("DELETE FROM tenant_invitations WHERE id = %s", (invitation_id,))
                    cursor.execute(
                        "DELETE FROM tenant_users WHERE tenant_id = %s AND user_id = %s",
                        (tenant["id"], target_user_id),
                    )
                    cursor.execute("DELETE FROM users WHERE id = %s", (target_user_id,))
                    cursor.execute("DELETE FROM request_throttle WHERE scope = 'tenant_owner_transfer'")
                    connection.commit()
                finally:
                    cursor.close()

    def test_login_and_logout_are_recorded_in_selected_store_activity(self):
        client = self._login("admin", "Admin@123")
        with get_connection() as connection:
            login_event = fetch_one(
                connection,
                "SELECT e.tenant_id, e.actor_user_id, e.details FROM audit_events e "
                "JOIN tenants t ON t.id = e.tenant_id "
                "WHERE t.slug = 'main' AND e.event_type = 'auth.login_succeeded' "
                "ORDER BY e.id DESC LIMIT 1",
            )
        self.assertIsNotNone(login_event)
        activity_page = client.get("/activity/")
        self.assertEqual(activity_page.status_code, 200)
        self.assertIn("Đăng nhập thành công", activity_page.get_data(as_text=True))

        token = self._csrf_token(client, "/dashboard")
        response = client.post("/logout", data={"csrf_token": token})
        self.assertEqual(response.status_code, 302)

        with get_connection() as connection:
            events = fetch_one(
                connection,
                "SELECT COUNT(*) total FROM audit_events WHERE tenant_id = %s "
                "AND actor_user_id = %s AND event_type IN ('auth.login_succeeded', 'auth.logout')",
                (login_event["tenant_id"], login_event["actor_user_id"]),
            )
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "DELETE FROM audit_events WHERE tenant_id = %s AND actor_user_id = %s "
                    "AND event_type IN ('auth.login_succeeded', 'auth.logout')",
                    (login_event["tenant_id"], login_event["actor_user_id"]),
                )
                connection.commit()
            finally:
                cursor.close()
        self.assertGreaterEqual(events["total"], 2)

    def test_password_change_revokes_existing_session_cookie(self):
        admin = self._login("admin", "Admin@123")
        staff = self._login("staff1", "Staff@123")
        with get_connection() as connection:
            staff_user = fetch_one(
                connection,
                "SELECT id, password_hash FROM users WHERE username = 'staff1'",
            )
        staff_id = staff_user["id"]
        try:
            response = admin.post(
                f"/users/{staff_id}/update",
                data={
                    "csrf_token": self._csrf_token(admin, "/users/"),
                    "full_name": "Nhân viên cửa hàng",
                    "role": "staff",
                    "active": "1",
                    "password": "Changed@123",
                },
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(staff.get("/dashboard").status_code, 302)

            changed_password_session = self._login("staff1", "Changed@123")
            self.assertEqual(changed_password_session.get("/dashboard").status_code, 200)

            response = admin.post(
                f"/users/{staff_id}/update",
                data={
                    "csrf_token": self._csrf_token(admin, "/users/"),
                    "full_name": "Nhân viên cửa hàng",
                    "role": "staff",
                    "active": "1",
                    "password": "Staff@123",
                },
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(changed_password_session.get("/dashboard").status_code, 302)
        finally:
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE users SET password_hash = %s, "
                        "session_version = session_version + 1 WHERE id = %s",
                        (staff_user["password_hash"], staff_id),
                    )
                    connection.commit()
                finally:
                    cursor.close()

    def test_verified_email_password_recovery_is_single_use_and_revokes_sessions(self):
        client = self._login("admin", "Admin@123")
        with get_connection() as connection:
            account = fetch_one(
                connection,
                "SELECT id, password_hash, email, email_verified_at FROM users WHERE username = 'admin'",
            )
        old_mail = {
            key: self.app.config.get(key)
            for key in ("MAIL_HOST", "MAIL_PORT", "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_FROM", "MAIL_FROM_NAME", "MAIL_STARTTLS", "MAIL_OUTBOX_KEY")
        }
        self.app.config.update(
            MAIL_HOST="smtp.example.test",
            MAIL_PORT=587,
            MAIL_USERNAME="",
            MAIL_PASSWORD="",
            MAIL_FROM="no-reply@example.test",
            MAIL_FROM_NAME="PetCare Manager",
            MAIL_STARTTLS=True,
            MAIL_OUTBOX_KEY=Fernet.generate_key().decode("ascii"),
        )
        sent_messages = []
        recovery_email = "admin-recovery@example.test"
        try:
            with patch(
                "petcare.services.account_security_service.enqueue_text_email",
                side_effect=lambda recipient, subject, body, **kwargs: sent_messages.append((recipient, subject, body)),
            ):
                response = client.post(
                    "/account/settings",
                    data={
                        "csrf_token": self._csrf_token(client, "/account/settings"),
                        "email": recovery_email,
                        "current_password": "Admin@123",
                    },
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(sent_messages[-1][0], recovery_email)
                verification_link = re.search(r"https?://\S+", sent_messages[-1][2]).group(0)
                verification_parts = urlsplit(verification_link)
                verification_url = verification_parts.path + "?" + verification_parts.query
                verification_page = client.get(verification_url)
                self.assertEqual(verification_page.status_code, 200)
                token = parse_qs(verification_parts.query)["token"][0]
                csrf = re.search(
                    r'name="csrf_token" value="([^"]+)"',
                    verification_page.get_data(as_text=True),
                ).group(1)
                confirmed = client.post(
                    verification_parts.path,
                    data={"csrf_token": csrf, "token": token},
                )
                self.assertEqual(confirmed.status_code, 302)

                with get_connection() as connection:
                    verified = fetch_one(
                        connection,
                        "SELECT email_verified_at FROM users WHERE id = %s",
                        (account["id"],),
                    )
                self.assertIsNotNone(verified["email_verified_at"])

                sent_messages.clear()
                response = client.post(
                    "/account/password/forgot",
                    data={
                        "csrf_token": self._csrf_token(client, "/account/password/forgot"),
                        "email": recovery_email,
                    },
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(sent_messages[-1][0], recovery_email)
                reset_link = re.search(r"https?://\S+", sent_messages[-1][2]).group(0)
                reset_parts = urlsplit(reset_link)
                reset_page = client.get(reset_parts.path + "?" + reset_parts.query)
                self.assertEqual(reset_page.status_code, 200)
                reset_token = parse_qs(reset_parts.query)["token"][0]
                reset_csrf = re.search(
                    r'name="csrf_token" value="([^"]+)"',
                    reset_page.get_data(as_text=True),
                ).group(1)
                reset = client.post(
                    reset_parts.path,
                    data={
                        "csrf_token": reset_csrf,
                        "token": reset_token,
                        "password": "Recovered@123",
                        "confirmation": "Recovered@123",
                    },
                )
                self.assertEqual(reset.status_code, 302)
                self.assertEqual(client.get("/dashboard").status_code, 302)
                recovered = self._login("admin", "Recovered@123")
                self.assertEqual(recovered.get("/dashboard").status_code, 200)

                replay = recovered.post(
                    reset_parts.path,
                    data={
                        "csrf_token": self._csrf_token(recovered, "/dashboard"),
                        "token": reset_token,
                        "password": "Another@123",
                        "confirmation": "Another@123",
                    },
                )
                self.assertEqual(replay.status_code, 404)
        finally:
            self.app.config.update(old_mail)
            secret = b"mysql-web-tests-only-secret"
            throttle_keys = []
            for scope, identity in (
                ("email_verification", account["id"]),
                ("email_verification_ip", "127.0.0.1"),
                ("password_reset", recovery_email),
                ("password_reset_ip", "127.0.0.1"),
            ):
                throttle_keys.append((hmac.new(
                    secret, f"api:{scope}:{str(identity)[:254]}".encode(), hashlib.sha256
                ).hexdigest(), scope))
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE users SET email = %s, email_verified_at = %s, password_hash = %s, "
                        "session_version = session_version + 1 WHERE id = %s",
                        (account["email"], account["email_verified_at"], account["password_hash"], account["id"]),
                    )
                    cursor.execute("DELETE FROM account_tokens WHERE user_id = %s", (account["id"],))
                    cursor.execute(
                        "DELETE FROM audit_events WHERE actor_user_id = %s "
                        "AND event_type LIKE 'account.%'",
                        (account["id"],),
                    )
                    for key_hash, scope in throttle_keys:
                        cursor.execute(
                            "DELETE FROM request_throttle WHERE key_hash = %s AND scope = %s",
                            (key_hash, scope),
                        )
                    connection.commit()
                finally:
                    cursor.close()

    def test_account_profile_requires_reauthentication_and_is_audited(self):
        suffix = uuid4().hex[:12]
        slug = "profile-" + suffix
        username = "profile_" + suffix
        password = "Profile@123"
        tenant_id, user_id = create_store(
            slug, "Profile " + suffix, username, "Profile Owner", password
        )
        client = self._login(username, password, slug)
        try:
            page = client.get("/account/settings")
            self.assertEqual(page.status_code, 200)
            self.assertIn("Tên này xuất hiện ở mọi cửa hàng bạn tham gia", page.get_data(as_text=True))

            invalid = client.post(
                "/account/profile",
                data={
                    "csrf_token": self._csrf_token(client, "/account/settings"),
                    "full_name": "Changed Name",
                    "current_password": "Wrong@123",
                },
            )
            self.assertEqual(invalid.status_code, 302)
            self.assertIn("Mật khẩu hiện tại chưa đúng", client.get(invalid.headers["Location"]).get_data(as_text=True))
            with get_connection() as connection:
                unchanged = fetch_one(connection, "SELECT full_name FROM users WHERE id = %s", (user_id,))
            self.assertEqual(unchanged["full_name"], "Profile Owner")

            updated = client.post(
                "/account/profile",
                data={
                    "csrf_token": self._csrf_token(client, "/account/settings"),
                    "full_name": "Updated Profile Owner",
                    "current_password": password,
                },
            )
            self.assertEqual(updated.status_code, 302)
            dashboard = client.get("/dashboard")
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn("Updated Profile Owner", dashboard.get_data(as_text=True))
            with get_connection() as connection:
                changed = fetch_one(connection, "SELECT full_name FROM users WHERE id = %s", (user_id,))
                event = fetch_one(
                    connection,
                    "SELECT summary, details FROM audit_events WHERE tenant_id = %s "
                    "AND actor_user_id = %s AND event_type = 'account.profile_updated' ORDER BY id DESC LIMIT 1",
                    (tenant_id, user_id),
                )
            self.assertEqual(changed["full_name"], "Updated Profile Owner")
            self.assertEqual(event["summary"], "Cập nhật tên hiển thị tài khoản")
            self.assertNotIn("Updated Profile Owner", str(event["details"]))
        finally:
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute("DELETE FROM audit_events WHERE tenant_id = %s AND actor_user_id = %s", (tenant_id, user_id))
                    cursor.execute("DELETE FROM tenant_users WHERE tenant_id = %s AND user_id = %s", (tenant_id, user_id))
                    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                    cursor.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
                    connection.commit()
                finally:
                    cursor.close()

    def test_encrypted_mail_outbox_retries_and_does_not_store_plaintext(self):
        old_mail = {
            key: self.app.config.get(key)
            for key in ("MAIL_HOST", "MAIL_PORT", "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_FROM", "MAIL_FROM_NAME", "MAIL_STARTTLS", "MAIL_OUTBOX_KEY")
        }
        self.app.config.update(
            MAIL_HOST="smtp.example.test",
            MAIL_PORT=587,
            MAIL_USERNAME="",
            MAIL_PASSWORD="",
            MAIL_FROM="no-reply@example.test",
            MAIL_FROM_NAME="PetCare Manager",
            MAIL_STARTTLS=True,
            MAIL_OUTBOX_KEY=Fernet.generate_key().decode("ascii"),
        )
        message_id = None
        secret_body = "https://example.test/reset?token=one-time-secret"
        recipient = "private-recipient@example.test"
        try:
            with self.app.app_context():
                message_id = enqueue_text_email(recipient, "Private subject", secret_body)
            with get_connection() as connection:
                stored = fetch_one(
                    connection,
                    "SELECT payload_ciphertext, status, attempt_count FROM email_outbox WHERE id = %s",
                    (message_id,),
                )
            self.assertEqual(stored["status"], "pending")
            ciphertext = bytes(stored["payload_ciphertext"])
            self.assertNotIn(recipient.encode(), ciphertext)
            self.assertNotIn(secret_body.encode(), ciphertext)

            with self.app.app_context(), patch(
                "petcare.services.mail_outbox_worker.send_text_email",
                side_effect=[MailDeliveryError("provider rejected message"), None],
            ) as send:
                self.assertTrue(dispatch_one(message_id))
                with get_connection() as connection:
                    cursor = connection.cursor()
                    try:
                        cursor.execute(
                            "UPDATE email_outbox SET next_attempt_at = CURRENT_TIMESTAMP WHERE id = %s",
                            (message_id,),
                        )
                        connection.commit()
                    finally:
                        cursor.close()
                with get_connection() as connection:
                    retried = fetch_one(
                        connection,
                        "SELECT status, attempt_count, last_error_code FROM email_outbox WHERE id = %s",
                        (message_id,),
                    )
                self.assertEqual(retried["status"], "pending")
                self.assertEqual(retried["attempt_count"], 1)
                self.assertEqual(retried["last_error_code"], "delivery_failed")

                self.assertTrue(dispatch_one(message_id))
                with get_connection() as connection:
                    sent = fetch_one(
                        connection,
                        "SELECT status, attempt_count, sent_at FROM email_outbox WHERE id = %s",
                        (message_id,),
                    )
                self.assertEqual(sent["status"], "sent")
                self.assertEqual(sent["attempt_count"], 2)
                self.assertIsNotNone(sent["sent_at"])
                self.assertEqual(send.call_count, 2)
        finally:
            self.app.config.update(old_mail)
            if message_id is not None:
                with get_connection() as connection:
                    cursor = connection.cursor()
                    try:
                        cursor.execute("DELETE FROM email_outbox WHERE id = %s", (message_id,))
                        connection.commit()
                    finally:
                        cursor.close()

    def test_expired_email_outbox_message_is_not_claimed(self):
        old_mail = {
            key: self.app.config.get(key)
            for key in ("MAIL_HOST", "MAIL_PORT", "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_FROM", "MAIL_FROM_NAME", "MAIL_STARTTLS", "MAIL_OUTBOX_KEY")
        }
        self.app.config.update(
            MAIL_HOST="smtp.example.test",
            MAIL_PORT=587,
            MAIL_USERNAME="",
            MAIL_PASSWORD="",
            MAIL_FROM="no-reply@example.test",
            MAIL_FROM_NAME="PetCare Manager",
            MAIL_STARTTLS=True,
            MAIL_OUTBOX_KEY=Fernet.generate_key().decode("ascii"),
        )
        message_id = None
        try:
            with self.app.app_context():
                message_id = enqueue_text_email(
                    "expired@example.test", "Expired", "Expired token link",
                    expires_at=datetime(2000, 1, 1),
                )
                with patch("petcare.services.mail_outbox_worker.send_text_email") as send:
                    self.assertFalse(dispatch_one(message_id))
                    send.assert_not_called()
            with get_connection() as connection:
                row = fetch_one(
                    connection,
                    "SELECT status, attempt_count FROM email_outbox WHERE id = %s",
                    (message_id,),
                )
            self.assertEqual(row["status"], "pending")
            self.assertEqual(row["attempt_count"], 0)
        finally:
            self.app.config.update(old_mail)
            if message_id is not None:
                with get_connection() as connection:
                    cursor = connection.cursor()
                    try:
                        cursor.execute("DELETE FROM email_outbox WHERE id = %s", (message_id,))
                        connection.commit()
                    finally:
                        cursor.close()

    def test_readiness_confirms_runtime_mysql_schema_and_tenant_constraints(self):
        response = self.app.test_client().get("/readyz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ready"})
        with get_connection() as connection:
            runtime = fetch_one(
                connection,
                "SELECT @@session.time_zone session_timezone, "
                "TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), CURRENT_TIMESTAMP) timezone_offset",
            )
            migration = fetch_one(
                connection,
                "SELECT version FROM schema_migrations WHERE version = %s",
                ("datetime_storage_utc_v1",),
            )
        self.assertEqual(runtime["session_timezone"], "+00:00")
        self.assertEqual(runtime["timezone_offset"], 0)
        self.assertIsNotNone(migration)

    def test_worker_health_requires_fresh_heartbeats_for_each_queue_worker(self):
        instance_ids = {"email": uuid4().hex, "tenant_export": uuid4().hex}
        stale_instance_id = uuid4().hex
        try:
            with transaction() as connection:
                for worker_name, instance_id in instance_ids.items():
                    worker_heartbeat_repo.touch(connection, worker_name, instance_id)
                worker_heartbeat_repo.touch(connection, "email", stale_instance_id)
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE worker_heartbeats SET last_seen_at = "
                        "DATE_SUB(UTC_TIMESTAMP(), INTERVAL 31 DAY) "
                        "WHERE worker_name = %s AND instance_id = %s",
                        ("email", stale_instance_id),
                    )
                finally:
                    cursor.close()
            with transaction() as connection:
                worker_heartbeat_repo.prune_stale(connection)
                stale_row = fetch_one(
                    connection,
                    "SELECT 1 FROM worker_heartbeats WHERE worker_name = %s AND instance_id = %s",
                    ("email", stale_instance_id),
                )
            self.assertIsNone(stale_row)
            response = self.app.test_client().get("/workersz")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json(), {"status": "ready"})

            with transaction() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE worker_heartbeats SET last_error_code = %s "
                        "WHERE worker_name = %s AND instance_id = %s",
                        ("worker_error", "email", instance_ids["email"]),
                    )
                finally:
                    cursor.close()
            response = self.app.test_client().get("/workersz")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.get_json(), {"status": "unavailable"})
        finally:
            with transaction() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "DELETE FROM worker_heartbeats WHERE "
                        "(worker_name, instance_id) IN ((%s, %s), (%s, %s), (%s, %s))",
                        (
                            "email", instance_ids["email"],
                            "tenant_export", instance_ids["tenant_export"],
                            "email", stale_instance_id,
                        ),
                    )
                finally:
                    cursor.close()

    def test_protected_metrics_endpoint_exposes_only_aggregate_queue_and_worker_state(self):
        token = "ops-metrics-test-" + uuid4().hex
        previous = self.app.config.get("OPS_METRICS_TOKEN", "")
        self.app.config["OPS_METRICS_TOKEN"] = token
        try:
            client = self.app.test_client()
            self.assertEqual(client.get("/metrics").status_code, 401)
            self.assertEqual(
                client.get(
                    "/metrics",
                    headers={"Authorization": "Bearer wrong-token"},
                ).status_code,
                401,
            )
            response = client.get(
                "/metrics",
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "text/plain")
            body = response.get_data(as_text=True)
            self.assertIn('petcare_queue_jobs{queue="email",status="pending"}', body)
            self.assertIn('petcare_queue_oldest_pending_seconds{queue="tenant_export"}', body)
            self.assertIn('petcare_worker_up{worker="tenant_export"}', body)
            self.assertNotIn("main", body)
            self.assertNotIn("@example", body)
            self.assertIn("no-store", response.headers["Cache-Control"])
        finally:
            self.app.config["OPS_METRICS_TOKEN"] = previous

    def test_runtime_pool_resets_tenant_context_between_connection_checkouts(self):
        pool_size = int(Config.DB_POOL_SIZE)
        held_connections = [get_connection() for _ in range(pool_size)]
        try:
            for connection in held_connections:
                cursor = connection.cursor()
                try:
                    cursor.execute("SET @petcare_tenant_id = 987654321")
                finally:
                    cursor.close()
        finally:
            for connection in held_connections:
                connection.close()

        for _ in range(pool_size):
            with get_connection() as connection:
                context = fetch_one(
                    connection,
                    "SELECT @petcare_tenant_id tenant_id, @@session.time_zone session_timezone",
                )
            self.assertIsNone(context["tenant_id"])
            self.assertEqual(context["session_timezone"], "+00:00")

    def test_public_signup_activates_new_store_only_after_email_verification(self):
        client = self.app.test_client()
        self.app.config["PUBLIC_SIGNUP_ENABLED"] = False
        self.assertEqual(client.get("/signup").status_code, 404)
        old_mail = {key: self.app.config.get(key) for key in ("MAIL_HOST", "MAIL_FROM")}
        self.app.config.update(
            PUBLIC_SIGNUP_ENABLED=True,
            MAIL_HOST="",
            MAIL_FROM="",
        )
        suffix = uuid4().hex[:12]
        username = "signup_" + suffix
        email = f"owner-{suffix}@example.test"
        slug = "signup-" + suffix
        user_id = tenant_id = None
        try:
            csrf = self._csrf_token(client, "/signup")
            response = client.post(
                "/signup",
                data={
                    "csrf_token": csrf,
                    "store_name": "Signup Store " + suffix,
                    "store_slug": slug,
                    "owner_name": "Signup Owner",
                    "username": username,
                    "email": email,
                    "password": "Signup@123",
                    "default_currency": "USD",
                    "timezone": "America/Los_Angeles",
                },
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            self.assertIn("CỬA HÀNG ĐÃ TẠO", html)
            self.assertIn(f"Dùng mã cửa hàng <strong>{slug}</strong>", html)
            token_match = re.search(
                r"/account/email/verify\?token=([A-Za-z0-9_-]{43})", html
            )
            self.assertIsNotNone(token_match)
            initialize_database()
            with get_connection() as connection:
                signup = fetch_one(
                    connection,
                    "SELECT u.id, u.email_verified_at, t.id tenant_id, t.default_currency, t.timezone, tu.active, "
                    "tu.email_activation_pending FROM users u "
                    "JOIN tenant_users tu ON tu.user_id = u.id "
                    "JOIN tenants t ON t.id = tu.tenant_id "
                    "WHERE u.username = %s AND t.slug = %s",
                    (username, slug),
                )
                memberships = fetch_one(
                    connection,
                    "SELECT COUNT(*) total FROM tenant_users WHERE user_id = %s",
                    (signup["id"],),
                )
            user_id, tenant_id = signup["id"], signup["tenant_id"]
            self.assertEqual(memberships["total"], 1)
            self.assertEqual(signup["default_currency"], "USD")
            self.assertEqual(signup["timezone"], "America/Los_Angeles")
            self.assertIsNone(signup["email_verified_at"])
            self.assertEqual(signup["active"], 0)
            self.assertEqual(signup["email_activation_pending"], 1)

            verify_path = f"/account/email/verify?token={token_match.group(1)}"
            verify_page = client.get(verify_path)
            self.assertEqual(verify_page.status_code, 200)
            verify_csrf = re.search(
                r'name="csrf_token" value="([^"]+)"',
                verify_page.get_data(as_text=True),
            )
            self.assertIsNotNone(verify_csrf)
            verified = client.post(
                "/account/email/verify",
                data={
                    "csrf_token": verify_csrf.group(1),
                    "token": token_match.group(1),
                },
            )
            self.assertEqual(verified.status_code, 302)
            with get_connection() as connection:
                membership = fetch_one(
                    connection,
                    "SELECT u.email_verified_at, tu.active, tu.email_activation_pending "
                    "FROM users u JOIN tenant_users tu ON tu.user_id = u.id "
                    "WHERE u.id = %s AND tu.tenant_id = %s",
                    (user_id, tenant_id),
                )
            self.assertIsNotNone(membership["email_verified_at"])
            self.assertEqual(membership["active"], 1)
            self.assertEqual(membership["email_activation_pending"], 0)
            owner = self._login(username, "Signup@123", slug)
            self.assertEqual(owner.get("/dashboard").status_code, 200)
        finally:
            self.app.config.update(PUBLIC_SIGNUP_ENABLED=False, **old_mail)
            if user_id and tenant_id:
                with get_connection() as connection:
                    cursor = connection.cursor()
                    try:
                        cursor.execute("DELETE FROM audit_events WHERE tenant_id = %s", (tenant_id,))
                        cursor.execute("DELETE FROM account_tokens WHERE user_id = %s", (user_id,))
                        cursor.execute("DELETE FROM tenant_users WHERE tenant_id = %s", (tenant_id,))
                        cursor.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
                        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                        connection.commit()
                    finally:
                        cursor.close()

    def test_public_signup_queues_encrypted_verification_before_exposing_store_access(self):
        client = self.app.test_client()
        original = {
            key: self.app.config.get(key)
            for key in ("PUBLIC_SIGNUP_ENABLED", "MAIL_HOST", "MAIL_FROM", "MAIL_OUTBOX_KEY")
        }
        key = Fernet.generate_key().decode("ascii")
        suffix = uuid4().hex[:12]
        username = "queued_signup_" + suffix
        email = f"queued-owner-{suffix}@example.test"
        slug = "queued-signup-" + suffix
        user_id = tenant_id = outbox_id = None
        try:
            self.app.config.update(
                PUBLIC_SIGNUP_ENABLED=True,
                MAIL_HOST="smtp.example.test",
                MAIL_FROM="noreply@example.test",
                MAIL_OUTBOX_KEY=key,
            )
            with get_connection() as connection:
                before = fetch_one(connection, "SELECT COALESCE(MAX(id), 0) latest FROM email_outbox")
            csrf = self._csrf_token(client, "/signup")
            response = client.post(
                "/signup",
                data={
                    "csrf_token": csrf,
                    "store_name": "Queued Signup " + suffix,
                    "store_slug": slug,
                    "owner_name": "Queued Owner",
                    "username": username,
                    "email": email,
                    "password": "Queued@123",
                },
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            self.assertIn("Mở email xác minh", html)
            self.assertNotRegex(html, r"/account/email/verify\?token=[A-Za-z0-9_-]{43}")
            with get_connection() as connection:
                signup = fetch_one(
                    connection,
                    "SELECT u.id, tu.active, tu.email_activation_pending, t.id tenant_id "
                    "FROM users u JOIN tenant_users tu ON tu.user_id = u.id "
                    "JOIN tenants t ON t.id = tu.tenant_id WHERE u.username = %s AND t.slug = %s",
                    (username, slug),
                )
                job = fetch_one(
                    connection,
                    "SELECT id, payload_ciphertext, status FROM email_outbox WHERE id > %s "
                    "ORDER BY id DESC LIMIT 1",
                    (before["latest"],),
                )
            user_id, tenant_id = signup["id"], signup["tenant_id"]
            outbox_id = job["id"]
            self.assertEqual((signup["active"], signup["email_activation_pending"]), (0, 1))
            self.assertEqual(job["status"], "pending")
            payload = json.loads(Fernet(key.encode("ascii")).decrypt(bytes(job["payload_ciphertext"])))
            self.assertEqual(payload["recipient"], email)
            token = re.search(r"token=([A-Za-z0-9_-]{43})", payload["body"])
            self.assertIsNotNone(token)
            with self.app.app_context(), patch("petcare.services.mail_outbox_worker.send_text_email"):
                self.assertTrue(dispatch_one(outbox_id))
            verify_page = client.get(f"/account/email/verify?token={token.group(1)}")
            csrf = re.search(
                r'name="csrf_token" value="([^"]+)"', verify_page.get_data(as_text=True)
            )
            self.assertEqual(verify_page.status_code, 200)
            self.assertIsNotNone(csrf)
            response = client.post(
                "/account/email/verify",
                data={"csrf_token": csrf.group(1), "token": token.group(1)},
            )
            self.assertEqual(response.status_code, 302)
            with get_connection() as connection:
                membership = fetch_one(
                    connection,
                    "SELECT active, email_activation_pending FROM tenant_users "
                    "WHERE user_id = %s AND tenant_id = %s",
                    (user_id, tenant_id),
                )
                message = fetch_one(
                    connection, "SELECT status FROM email_outbox WHERE id = %s", (outbox_id,)
                )
            self.assertEqual(membership, {"active": 1, "email_activation_pending": 0})
            self.assertEqual(message["status"], "sent")
        finally:
            self.app.config.update(original)
            if user_id and tenant_id:
                with get_connection() as connection:
                    cursor = connection.cursor()
                    try:
                        cursor.execute("DELETE FROM audit_events WHERE tenant_id = %s", (tenant_id,))
                        cursor.execute("DELETE FROM account_tokens WHERE user_id = %s", (user_id,))
                        cursor.execute("DELETE FROM tenant_users WHERE tenant_id = %s", (tenant_id,))
                        cursor.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
                        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                        if outbox_id:
                            cursor.execute("DELETE FROM email_outbox WHERE id = %s", (outbox_id,))
                        connection.commit()
                    finally:
                        cursor.close()

    def test_expired_unverified_signup_cleanup_removes_only_unclaimed_store(self):
        old = {
            key: self.app.config.get(key)
            for key in ("PUBLIC_SIGNUP_ENABLED", "MAIL_HOST", "MAIL_FROM")
        }
        self.app.config.update(PUBLIC_SIGNUP_ENABLED=True, MAIL_HOST="", MAIL_FROM="")
        suffix = uuid4().hex[:12]
        username = "expired_signup_" + suffix
        slug = "expired-signup-" + suffix
        user_id = tenant_id = None
        try:
            client = self.app.test_client()
            csrf = self._csrf_token(client, "/signup")
            response = client.post(
                "/signup",
                data={
                    "csrf_token": csrf,
                    "store_name": "Expired Signup " + suffix,
                    "store_slug": slug,
                    "owner_name": "Expired Owner",
                    "username": username,
                    "email": f"expired-{suffix}@example.test",
                    "password": "Expired@123",
                },
            )
            self.assertEqual(response.status_code, 200)
            with get_connection() as connection:
                signup = fetch_one(
                    connection,
                    "SELECT u.id, t.id tenant_id FROM users u "
                    "JOIN tenant_users tu ON tu.user_id = u.id "
                    "JOIN tenants t ON t.id = tu.tenant_id "
                    "WHERE u.username = %s AND t.slug = %s",
                    (username, slug),
                )
            user_id, tenant_id = signup["id"], signup["tenant_id"]
            with transaction() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE tenant_users SET created_at = DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 8 DAY) "
                        "WHERE tenant_id = %s AND user_id = %s",
                        (tenant_id, user_id),
                    )
                finally:
                    cursor.close()
                self.assertEqual(cleanup_expired_public_signups(connection), 1)
            with get_connection() as connection:
                self.assertIsNone(fetch_one(connection, "SELECT id FROM tenants WHERE id = %s", (tenant_id,)))
                self.assertIsNone(fetch_one(connection, "SELECT id FROM users WHERE id = %s", (user_id,)))
            tenant_id = user_id = None
        finally:
            self.app.config.update(old)
            if tenant_id and user_id:
                with get_connection() as connection:
                    cursor = connection.cursor()
                    try:
                        cursor.execute("DELETE FROM audit_events WHERE tenant_id = %s", (tenant_id,))
                        cursor.execute("DELETE FROM account_tokens WHERE user_id = %s", (user_id,))
                        cursor.execute("DELETE FROM tenant_users WHERE tenant_id = %s", (tenant_id,))
                        cursor.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
                        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                        connection.commit()
                    finally:
                        cursor.close()

    def test_additive_migration_installs_signup_cleanup_index(self):
        with get_connection() as connection:
            index = fetch_one(
                connection,
                "SELECT COUNT(*) total FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = 'tenant_users' "
                "AND index_name = 'idx_tenant_signup_cleanup'",
            )
        self.assertGreater(index["total"], 0)

    def test_invitation_creates_member_and_is_single_use(self):
        admin = self._login("admin", "Admin@123")
        invite_email = f"invite-{uuid4().hex}@example.test"
        invite_url = self._create_invitation(admin, "staff", invite_email)
        duplicate_csrf = self._csrf_token(admin, "/users/")
        duplicate = admin.post(
            "/users/invitations",
            data={"csrf_token": duplicate_csrf, "email": invite_email, "role": "admin"},
            follow_redirects=True,
        )
        self.assertIn("đã có lời mời đang chờ", duplicate.get_data(as_text=True))
        invite_client = self.app.test_client()
        response = invite_client.get(invite_url)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        token = re.search(r'name="token" value="([A-Za-z0-9_-]{43})"', html)
        self.assertIsNotNone(token)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', html)
        self.assertIsNotNone(csrf)
        username = "invite_" + uuid4().hex[:12]
        accepted = invite_client.post(
            "/users/invitations/accept",
            data={
                "csrf_token": csrf.group(1),
                "token": token.group(1),
                "username": username,
                "password": "Invited@123",
                "full_name": "New Store Staff",
            },
        )
        self.assertEqual(accepted.status_code, 302)
        dashboard = invite_client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Cửa hàng", dashboard.get_data(as_text=True))
        with get_connection() as connection:
            membership = fetch_one(
                connection,
                "SELECT tu.role, ti.accepted_at FROM users u "
                "JOIN tenant_users tu ON tu.user_id = u.id "
                "JOIN tenants t ON t.id = tu.tenant_id "
                "JOIN tenant_invitations ti ON ti.accepted_by = u.id AND ti.tenant_id = t.id "
                "WHERE u.username = %s AND t.slug = 'main'",
                (username,),
            )
        self.assertEqual(membership["role"], "staff")
        self.assertIsNotNone(membership["accepted_at"])
        with get_connection() as connection:
            invited_user = fetch_one(
                connection,
                "SELECT email, email_verified_at FROM users WHERE username = %s",
                (username,),
            )
        self.assertEqual(invited_user["email"], invite_email)
        self.assertIsNone(invited_user["email_verified_at"])
        self.assertEqual(invite_client.get(invite_url).status_code, 404)
        with get_connection() as connection:
            invitation = fetch_one(
                connection,
                "SELECT id FROM tenant_invitations WHERE token_hash = SHA2(%s, 256)",
                (token.group(1),),
            )
            user = fetch_one(connection, "SELECT id FROM users WHERE username = %s", (username,))
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "DELETE FROM audit_events WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'main') "
                    "AND ((entity_type = 'invitation' AND entity_id = %s) OR actor_user_id = %s)",
                    (invitation["id"], user["id"]),
                )
                cursor.execute("DELETE FROM tenant_invitations WHERE id = %s", (invitation["id"],))
                cursor.execute("DELETE FROM tenant_users WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'main') AND user_id = %s", (user["id"],))
                cursor.execute("DELETE FROM users WHERE id = %s", (user["id"],))
                connection.commit()
            finally:
                cursor.close()

    def test_invitation_can_attach_existing_account_or_be_revoked(self):
        suffix = uuid4().hex[:12]
        username = "invite_owner_" + suffix
        password = "Existing@123"
        other_slug = "invite-store-" + suffix
        tenant_id, user_id = create_store(
            other_slug, "Invite store " + suffix, username, "Existing Owner", password
        )
        invited_email = f"existing-invite-{suffix}@example.test"
        with get_connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "UPDATE users SET email = %s, email_verified_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (invited_email, user_id),
                )
                connection.commit()
            finally:
                cursor.close()
        admin = self._login("admin", "Admin@123")
        invite_url = self._create_invitation(admin, "admin", invited_email)
        invite_client = self.app.test_client()
        page = invite_client.get(invite_url)
        token = re.search(r'name="token" value="([A-Za-z0-9_-]{43})"', page.get_data(as_text=True))
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True))
        self.assertIsNotNone(token)
        self.assertIsNotNone(csrf)
        wrong_account = invite_client.post(
            "/users/invitations/accept",
            data={
                "csrf_token": csrf.group(1),
                "token": token.group(1),
                "username": "admin",
                "password": "Admin@123",
                "full_name": "",
            },
        )
        self.assertEqual(wrong_account.status_code, 200)
        self.assertIn("đúng email lời mời", wrong_account.get_data(as_text=True))
        accepted = invite_client.post(
            "/users/invitations/accept",
            data={
                "csrf_token": csrf.group(1),
                "token": token.group(1),
                "username": username,
                "password": password,
                "full_name": "",
            },
        )
        self.assertEqual(accepted.status_code, 302)
        accepted_token = invite_url.split("token=", 1)[1]
        with get_connection() as connection:
            membership = fetch_one(
                connection,
                "SELECT role, active FROM tenant_users WHERE tenant_id = "
                "(SELECT id FROM tenants WHERE slug = 'main') AND user_id = %s",
                (user_id,),
            )
        self.assertEqual(membership, {"role": "admin", "active": 1})

        revoke_url = self._create_invitation(admin, "staff")
        revoke_token = revoke_url.split("token=", 1)[1]
        with get_connection() as connection:
            invite = fetch_one(
                connection,
                "SELECT id FROM tenant_invitations WHERE token_hash = SHA2(%s, 256)",
                (revoke_token,),
            )
        csrf = self._csrf_token(admin, "/users/")
        response = admin.post(
            f"/users/invitations/{invite['id']}/revoke",
            data={"csrf_token": csrf},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.app.test_client().get(revoke_url).status_code, 404)
        revoke_id = invite["id"]
        with get_connection() as connection:
            accepted_invite = fetch_one(
                connection,
                "SELECT id FROM tenant_invitations WHERE token_hash = SHA2(%s, 256)",
                (accepted_token,),
            )
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "DELETE FROM audit_events WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'main') "
                    "AND ((entity_type = 'invitation' AND entity_id IN (%s, %s)) OR actor_user_id = %s)",
                    (accepted_invite["id"], revoke_id, user_id),
                )
                cursor.execute(
                    "DELETE FROM tenant_invitations WHERE id IN (%s, %s)",
                    (accepted_invite["id"], revoke_id),
                )
                cursor.execute(
                    "DELETE FROM tenant_users WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'main') AND user_id = %s",
                    (user_id,),
                )
                connection.commit()
            finally:
                cursor.close()
        with get_connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute("DELETE FROM audit_events WHERE tenant_id = %s", (tenant_id,))
                cursor.execute("DELETE FROM tenant_users WHERE tenant_id = %s", (tenant_id,))
                cursor.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
                cursor.execute(
                    "DELETE FROM users WHERE id = %s AND NOT EXISTS "
                    "(SELECT 1 FROM tenant_users WHERE user_id = %s)",
                    (user_id, user_id),
                )
                connection.commit()
            finally:
                cursor.close()

    def test_configured_invitation_email_is_encrypted_and_not_exposed_to_admin(self):
        admin = self._login("admin", "Admin@123")
        old = {
            key: self.app.config.get(key)
            for key in ("MAIL_HOST", "MAIL_FROM", "MAIL_OUTBOX_KEY")
        }
        key = Fernet.generate_key().decode("ascii")
        email = f"queued-invite-{uuid4().hex}@example.test"
        invitation_id = None
        outbox_id = None
        try:
            self.app.config.update(
                MAIL_HOST="smtp.example.test",
                MAIL_FROM="noreply@example.test",
                MAIL_OUTBOX_KEY=key,
            )
            csrf = self._csrf_token(admin, "/users/")
            response = admin.post(
                "/users/invitations",
                data={"csrf_token": csrf, "email": email, "role": "staff"},
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            self.assertIn("xếp lời mời vào hàng gửi email", html)
            self.assertNotRegex(html, r"/users/invitations/accept\?token=[A-Za-z0-9_-]{43}")
            with get_connection() as connection:
                invitation = fetch_one(
                    connection,
                    "SELECT id, email, email_outbox_id FROM tenant_invitations "
                    "WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'main') "
                    "AND email = %s ORDER BY id DESC LIMIT 1",
                    (email,),
                )
                self.assertEqual(invitation["email"], email)
                invitation_id = invitation["id"]
                outbox_id = invitation["email_outbox_id"]
                message = fetch_one(
                    connection,
                    "SELECT payload_ciphertext, status FROM email_outbox WHERE id = %s",
                    (outbox_id,),
                )
            self.assertEqual(message["status"], "pending")
            self.assertNotIn(email.encode("utf-8"), bytes(message["payload_ciphertext"]))
            payload = json.loads(Fernet(key.encode("ascii")).decrypt(bytes(message["payload_ciphertext"])))
            self.assertEqual(payload["recipient"], email)
            self.assertIn("/users/invitations/accept?token=", payload["body"])
            token = re.search(r"token=([A-Za-z0-9_-]{43})", payload["body"])
            self.assertIsNotNone(token)
            invite_page = self.app.test_client().get(
                f"/users/invitations/accept?token={token.group(1)}"
            )
            self.assertEqual(invite_page.status_code, 200)
            self.assertEqual(invite_page.headers.get("Cache-Control"), "private, no-store, max-age=0")
            self.assertEqual(invite_page.headers.get("Referrer-Policy"), "no-referrer")
        finally:
            self.app.config.update(old)
            if invitation_id:
                with get_connection() as connection:
                    cursor = connection.cursor()
                    try:
                        cursor.execute(
                            "DELETE FROM audit_events WHERE entity_type = 'invitation' AND entity_id = %s",
                            (invitation_id,),
                        )
                        cursor.execute("DELETE FROM tenant_invitations WHERE id = %s", (invitation_id,))
                        if outbox_id:
                            cursor.execute("DELETE FROM email_outbox WHERE id = %s", (outbox_id,))
                        connection.commit()
                    finally:
                        cursor.close()

    def test_tenant_export_is_private_checksummed_and_isolated(self):
        suffix = uuid4().hex[:12]
        slug = "export-" + suffix
        username = "export_owner_" + suffix
        tenant_id, user_id = create_store(
            slug, "Export store " + suffix, username, "Export Owner", "Export@123"
        )
        product_code = "EXPORT-" + suffix.upper()
        with get_connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "INSERT INTO products (tenant_id, code, name, category, unit_price, stock_qty) "
                    "VALUES (%s, %s, %s, 'Test', 1250, 3)",
                    (tenant_id, product_code, "PRIVATE TENANT MARKER " + suffix),
                )
                connection.commit()
            finally:
                cursor.close()
        probe_customer_id = None
        try:
            formula_name = '=HYPERLINK("https://example.invalid","open")'
            formula_phone = "9" + str(int(suffix, 16)).zfill(11)[-11:]
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute("SELECT id FROM tenants WHERE slug = 'main'")
                    main_tenant_id = cursor.fetchone()[0]
                    cursor.execute(
                        "INSERT INTO customers (tenant_id, full_name, phone) VALUES (%s, %s, %s)",
                        (main_tenant_id, formula_name, formula_phone),
                    )
                    probe_customer_id = cursor.lastrowid
                    connection.commit()
                finally:
                    cursor.close()
            with tempfile.TemporaryDirectory() as directory:
                archive_path = os.path.join(directory, "store-export.pcarexport")
                plaintext_path = os.path.join(directory, "store-export.zip")
                export_passphrase = "Integration-export-passphrase-2026"
                result = export_tenant("main", archive_path, export_passphrase)
                self.assertEqual(stat.S_IMODE(os.stat(archive_path).st_mode), 0o600)
                self.assertEqual(result["tenant_slug"], "main")
                self.assertTrue(result["encrypted"])
                manifest = verify_encrypted_tenant_export(archive_path, export_passphrase)
                self.assertEqual(manifest["format"], "petcare-tenant-export-v1")
                decrypt_tenant_export(archive_path, plaintext_path, export_passphrase)
                with zipfile.ZipFile(plaintext_path) as archive:
                    self.assertIsNone(archive.testzip())
                    manifest = json.loads(archive.read("manifest.json"))
                    self.assertEqual(manifest["format"], "petcare-tenant-export-v1")
                    self.assertEqual(manifest["tenant_slug"], "main")
                    for name, expected in manifest["sha256"].items():
                        self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), expected)
                    products_csv = archive.read("data/products.csv").decode("utf-8")
                    customers_csv = archive.read("data/customers.csv").decode("utf-8")
                    users_csv = archive.read("data/memberships.csv").decode("utf-8")
                    invitations_csv = archive.read("data/invitations.csv").decode("utf-8")
                    owner_transfers_csv = archive.read("data/owner_transfers.csv").decode("utf-8")
                    exported_customers = list(csv.DictReader(StringIO(customers_csv)))
                    exported_probe = next(
                        customer for customer in exported_customers
                        if customer["phone"] == formula_phone
                    )
                    self.assertEqual(exported_probe["full_name"], "'" + formula_name)
                    self.assertNotIn("PRIVATE TENANT MARKER", products_csv)
                    self.assertNotIn("password_hash", users_csv)
                    self.assertNotIn("pbkdf2_sha256$", users_csv)
                    self.assertNotIn("token_hash", invitations_csv)
                    owner_transfer_reader = csv.DictReader(StringIO(owner_transfers_csv))
                    self.assertEqual(owner_transfer_reader.fieldnames, [
                        "id", "requested_by_username", "target_username", "created_at",
                        "expires_at", "accepted_at", "cancelled_at",
                    ])
                    self.assertIn("excluded_secrets", manifest)
                with self.assertRaises(FileExistsError):
                    export_tenant("main", archive_path, export_passphrase)
        finally:
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    if probe_customer_id is not None:
                        cursor.execute(
                            "DELETE FROM customers WHERE id = %s AND tenant_id = "
                            "(SELECT id FROM tenants WHERE slug = 'main')",
                            (probe_customer_id,),
                        )
                    cursor.execute("DELETE FROM products WHERE tenant_id = %s AND code = %s", (tenant_id, product_code))
                    cursor.execute("DELETE FROM audit_events WHERE tenant_id = %s", (tenant_id,))
                    cursor.execute("DELETE FROM tenant_users WHERE tenant_id = %s", (tenant_id,))
                    cursor.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
                    cursor.execute(
                        "DELETE FROM users WHERE id = %s AND NOT EXISTS "
                        "(SELECT 1 FROM tenant_users WHERE user_id = %s)",
                        (user_id, user_id),
                    )
                    connection.commit()
                finally:
                    cursor.close()

    def test_store_admin_can_download_encrypted_export_with_step_up_auth(self):
        suffix = uuid4().hex[:12]
        slug = "self-export-" + suffix
        username = "self_export_owner_" + suffix
        tenant_id, user_id = create_store(
            slug, "Self export store " + suffix, username, "Export Owner", "Export@123"
        )
        product_code = "SELF-EXPORT-" + suffix.upper()
        with get_connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "INSERT INTO products (tenant_id, code, name, category, unit_price, stock_qty) "
                    "VALUES (%s, %s, %s, 'Test', 1250, 3)",
                    (tenant_id, product_code, "PRIVATE SELF EXPORT " + suffix),
                )
                connection.commit()
            finally:
                cursor.close()

        old_limit = self.app.config["TENANT_EXPORT_RATE_LIMIT_PER_MINUTE"]
        old_export_dir = self.app.config.get("TENANT_EXPORT_DIR")
        old_export_key = self.app.config.get("TENANT_EXPORT_JOB_KEY", "")
        old_export_backend = self.app.config.get("TENANT_EXPORT_STORAGE_BACKEND", "local")
        self.app.config["TENANT_EXPORT_RATE_LIMIT_PER_MINUTE"] = 10
        self.app.config["TENANT_EXPORT_JOB_KEY"] = Fernet.generate_key().decode("ascii")
        self.app.config["TENANT_EXPORT_STORAGE_BACKEND"] = "local"
        client = self._login(username, "Export@123", store_slug=slug)
        export_passphrase = "Store-owner-export-passphrase-2026"
        job_id = None
        try:
            with tempfile.TemporaryDirectory(prefix="tenant-export-test-") as export_dir:
                self.app.config["TENANT_EXPORT_DIR"] = export_dir
                page = client.get("/users/export")
                self.assertEqual(page.status_code, 200)
                self.assertIn("Yêu cầu xuất dữ liệu", page.get_data(as_text=True))
                self.assertEqual(page.headers.get("Cache-Control"), "private, no-store, max-age=0")

                staff = self._login("staff1", "Staff@123")
                self.assertEqual(staff.get("/users/export").status_code, 403)

                invalid_password = client.post(
                    "/users/export",
                    data={
                        "csrf_token": self._csrf_token(client, "/users/export"),
                        "current_password": "incorrect-password",
                        "passphrase": export_passphrase,
                        "passphrase_confirmation": export_passphrase,
                    },
                )
                self.assertEqual(invalid_password.status_code, 400)
                self.assertIn("Mật khẩu hiện tại không đúng", invalid_password.get_data(as_text=True))

                mismatch = client.post(
                    "/users/export",
                    data={
                        "csrf_token": self._csrf_token(client, "/users/export"),
                        "current_password": "Export@123",
                        "passphrase": export_passphrase,
                        "passphrase_confirmation": "Different-export-passphrase-2026",
                    },
                )
                self.assertEqual(mismatch.status_code, 400)

                queued = client.post(
                    "/users/export",
                    data={
                        "csrf_token": self._csrf_token(client, "/users/export"),
                        "current_password": "Export@123",
                        "passphrase": export_passphrase,
                        "passphrase_confirmation": export_passphrase,
                    },
                )
                self.assertEqual(queued.status_code, 302)
                self.assertIn("/users/export/jobs/", queued.headers["Location"])
                job_id = int(urlsplit(queued.headers["Location"]).path.rsplit("/", 1)[1])
                status_page = client.get(queued.headers["Location"])
                self.assertEqual(status_page.status_code, 200)
                self.assertEqual(status_page.headers.get("Cache-Control"), "private, no-store, max-age=0")

                with get_connection() as connection:
                    cursor = connection.cursor()
                    try:
                        cursor.execute(
                            "SELECT status, passphrase_ciphertext FROM tenant_export_jobs "
                            "WHERE id = %s AND tenant_id = %s",
                            (job_id, tenant_id),
                        )
                        queued_row = cursor.fetchone()
                        self.assertEqual(queued_row[0], "pending")
                        self.assertNotIn(export_passphrase.encode(), bytes(queued_row[1]))
                    finally:
                        cursor.close()

                with self.app.app_context():
                    self.assertTrue(process_tenant_export_one(job_id))

                other_store_admin = self._login("admin", "Admin@123")
                self.assertEqual(other_store_admin.get(queued.headers["Location"]).status_code, 404)
                state = client.get(f"/users/export/jobs/{job_id}/status")
                self.assertEqual(state.status_code, 200)
                if state.get_json()["status"] != "ready":
                    with get_connection() as connection:
                        cursor = connection.cursor()
                        try:
                            cursor.execute(
                                "SELECT status, last_error_code, attempt_count "
                                "FROM tenant_export_jobs WHERE id = %s",
                                (job_id,),
                            )
                            diagnostic = cursor.fetchone()
                        finally:
                            cursor.close()
                    self.fail(f"Export worker did not produce a ready artifact: {state.get_json()}, {diagnostic}")
                self.assertEqual(state.headers.get("Cache-Control"), "private, no-store, max-age=0")

                download_url = state.get_json()["download_url"]
                interrupted = client.get(download_url, buffered=False)
                self.assertEqual(interrupted.status_code, 200)
                interrupted.close()
                response = client.get(download_url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers.get("Cache-Control"), "private, no-store, max-age=0")
                self.assertIn("petcare-export-", response.headers["Content-Disposition"])
                encrypted_bytes = response.get_data()
                self.assertTrue(encrypted_bytes.startswith(b"PCEXP001"))
                self.assertNotIn(b"PRIVATE SELF EXPORT", encrypted_bytes)
                with tempfile.TemporaryDirectory() as directory:
                    encrypted_path = os.path.join(directory, "store.pcarexport")
                    with open(encrypted_path, "wb") as output:
                        output.write(encrypted_bytes)
                    manifest = verify_encrypted_tenant_export(encrypted_path, export_passphrase)
                    self.assertEqual(manifest["tenant_slug"], slug)
                    self.assertEqual(manifest["tables"]["products"], 1)

                self.app.config["TENANT_EXPORT_RATE_LIMIT_PER_MINUTE"] = 3
                limited = client.post(
                    "/users/export",
                    data={
                        "csrf_token": self._csrf_token(client, "/users/export"),
                        "current_password": "Export@123",
                        "passphrase": export_passphrase,
                        "passphrase_confirmation": export_passphrase,
                    },
                )
                self.assertEqual(limited.status_code, 429)
                self.assertGreaterEqual(int(limited.headers["Retry-After"]), 1)

                with get_connection() as connection:
                    cursor = connection.cursor()
                    try:
                        cursor.execute(
                            "SELECT COUNT(*) FROM audit_events WHERE tenant_id = %s "
                            "AND event_type = 'tenant.exported'",
                            (tenant_id,),
                        )
                        self.assertEqual(cursor.fetchone()[0], 1)
                        cursor.execute(
                            "SELECT status, passphrase_ciphertext, artifact_size "
                            "FROM tenant_export_jobs WHERE id = %s",
                            (job_id,),
                        )
                        ready_row = cursor.fetchone()
                        self.assertEqual(ready_row[0], "ready")
                        self.assertIsNone(ready_row[1])
                        self.assertEqual(ready_row[2], len(encrypted_bytes))
                    finally:
                        cursor.close()
        finally:
            self.app.config["TENANT_EXPORT_RATE_LIMIT_PER_MINUTE"] = old_limit
            self.app.config["TENANT_EXPORT_DIR"] = old_export_dir
            self.app.config["TENANT_EXPORT_JOB_KEY"] = old_export_key
            self.app.config["TENANT_EXPORT_STORAGE_BACKEND"] = old_export_backend
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute("DELETE FROM audit_events WHERE tenant_id = %s", (tenant_id,))
                    cursor.execute("DELETE FROM tenant_export_jobs WHERE tenant_id = %s", (tenant_id,))
                    export_key = hmac.new(
                        b"mysql-web-tests-only-secret",
                        f"api:tenant_export:{user_id}".encode(),
                        hashlib.sha256,
                    ).hexdigest()
                    cursor.execute(
                        "DELETE FROM request_throttle WHERE key_hash = %s AND scope = 'tenant_export'",
                        (export_key,),
                    )
                    cursor.execute("DELETE FROM products WHERE tenant_id = %s AND code = %s", (tenant_id, product_code))
                    cursor.execute("DELETE FROM tenant_users WHERE tenant_id = %s", (tenant_id,))
                    cursor.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
                    cursor.execute(
                        "DELETE FROM users WHERE id = %s AND NOT EXISTS "
                        "(SELECT 1 FROM tenant_users WHERE user_id = %s)",
                        (user_id, user_id),
                    )
                    connection.commit()
                finally:
                    cursor.close()
    def test_catalog_and_invoice_lists_use_bounded_mysql_pages(self):
        admin = self._login("admin", "Admin@123")
        paths = (
            "/customers/?q=Kh%C3%A1ch&page=9999999",
            "/products/?all=1&page=not-a-page",
            "/pets/?status=available&page=9999999",
            "/invoices/?status=paid&page=9999999",
        )
        for path in paths:
            with self.subTest(path=path):
                response = admin.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("Hiển thị", response.get_data(as_text=True))

    def test_ai_and_image_routes_enforce_shared_mysql_quotas(self):
        admin = self._login("admin", "Admin@123")
        token = self._csrf_token(admin, "/dashboard")
        with get_connection() as connection:
            user = fetch_one(connection, "SELECT id FROM users WHERE username = 'admin'")
        scopes = ("assistant", "assistant_ip", "vision", "vision_ip")
        identities = {
            "assistant": str(user["id"]),
            "assistant_ip": "127.0.0.1",
            "vision": str(user["id"]),
            "vision_ip": "127.0.0.1",
        }
        keys = {
            scope: hmac.new(
                self.app.config["SECRET_KEY"].encode("utf-8"),
                f"api:{scope}:{identities[scope]}".encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            for scope in scopes
        }
        with get_connection() as connection:
            cursor = connection.cursor()
            try:
                for scope, key in keys.items():
                    cursor.execute(
                        "DELETE FROM request_throttle WHERE key_hash = %s AND scope = %s",
                        (key, scope),
                    )
                connection.commit()
            finally:
                cursor.close()
        self.app.config.update(
            ASSISTANT_RATE_LIMIT_PER_MINUTE=2,
            ASSISTANT_IP_RATE_LIMIT_PER_MINUTE=120,
            VISION_RATE_LIMIT_PER_MINUTE=1,
            VISION_IP_RATE_LIMIT_PER_MINUTE=40,
        )
        try:
            for _ in range(2):
                response = admin.post(
                    "/assistant/chat",
                    json={"message": "Doanh thu hôm nay?"},
                    headers={"X-CSRFToken": token},
                )
                self.assertEqual(response.status_code, 200)
            assistant_limited = admin.post(
                "/assistant/chat",
                json={"message": "Doanh thu hôm nay?"},
                headers={"X-CSRFToken": token},
            )
            self.assertEqual(assistant_limited.status_code, 429)
            self.assertGreater(int(assistant_limited.headers["Retry-After"]), 0)

            image_token = self._csrf_token(admin, "/pets/find-similar")
            first_scan = admin.post(
                "/pets/find-similar",
                data={"csrf_token": image_token, "photo": (BytesIO(b""), "")},
                content_type="multipart/form-data",
            )
            self.assertEqual(first_scan.status_code, 200)
            second_scan = admin.post(
                "/pets/find-similar",
                data={"csrf_token": image_token, "photo": (BytesIO(b""), "")},
                content_type="multipart/form-data",
            )
            self.assertEqual(second_scan.status_code, 429)
            self.assertGreater(int(second_scan.headers["Retry-After"]), 0)
        finally:
            self.app.config.update(
                ASSISTANT_RATE_LIMIT_PER_MINUTE=20,
                ASSISTANT_IP_RATE_LIMIT_PER_MINUTE=120,
                VISION_RATE_LIMIT_PER_MINUTE=8,
                VISION_IP_RATE_LIMIT_PER_MINUTE=40,
            )
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    for scope, key in keys.items():
                        cursor.execute(
                            "DELETE FROM request_throttle WHERE key_hash = %s AND scope = %s",
                            (key, scope),
                        )
                    connection.commit()
                finally:
                    cursor.close()

    def test_ai_and_vision_network_quotas_are_shared_across_accounts(self):
        admin = self._login("admin", "Admin@123")
        staff = self._login("staff1", "Staff@123")
        with get_connection() as connection:
            admin_user = fetch_one(connection, "SELECT id FROM users WHERE username = 'admin'")
            staff_user = fetch_one(connection, "SELECT id FROM users WHERE username = 'staff1'")
        identities = [
            ("assistant", str(admin_user["id"])),
            ("assistant", str(staff_user["id"])),
            ("vision", str(admin_user["id"])),
            ("vision", str(staff_user["id"])),
            ("assistant_ip", "127.0.0.1"),
            ("vision_ip", "127.0.0.1"),
        ]
        keys = [
            (
                scope,
                hmac.new(
                    self.app.config["SECRET_KEY"].encode("utf-8"),
                    f"api:{scope}:{identity}".encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest(),
            )
            for scope, identity in identities
        ]

        def clear_test_keys():
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    for scope, key in keys:
                        cursor.execute(
                            "DELETE FROM request_throttle WHERE key_hash = %s AND scope = %s",
                            (key, scope),
                        )
                    connection.commit()
                finally:
                    cursor.close()

        clear_test_keys()
        previous_values = {
            name: self.app.config[name]
            for name in (
                "ASSISTANT_RATE_LIMIT_PER_MINUTE", "ASSISTANT_IP_RATE_LIMIT_PER_MINUTE",
                "VISION_RATE_LIMIT_PER_MINUTE", "VISION_IP_RATE_LIMIT_PER_MINUTE",
            )
        }
        self.app.config.update(
            ASSISTANT_RATE_LIMIT_PER_MINUTE=100,
            ASSISTANT_IP_RATE_LIMIT_PER_MINUTE=2,
            VISION_RATE_LIMIT_PER_MINUTE=100,
            VISION_IP_RATE_LIMIT_PER_MINUTE=2,
        )
        try:
            admin_token = self._csrf_token(admin, "/dashboard")
            staff_token = self._csrf_token(staff, "/dashboard")
            for client, token in ((admin, admin_token), (staff, staff_token)):
                response = client.post(
                    "/assistant/chat",
                    json={"message": "Doanh thu hôm nay?"},
                    headers={"X-CSRFToken": token},
                )
                self.assertEqual(response.status_code, 200)
            assistant_limited = admin.post(
                "/assistant/chat",
                json={"message": "Doanh thu hôm nay?"},
                headers={"X-CSRFToken": admin_token},
            )
            self.assertEqual(assistant_limited.status_code, 429)

            admin_image_token = self._csrf_token(admin, "/pets/find-similar")
            staff_image_token = self._csrf_token(staff, "/pets/find-similar")
            for client, token in ((admin, admin_image_token), (staff, staff_image_token)):
                response = client.post(
                    "/pets/find-similar",
                    data={"csrf_token": token, "photo": (BytesIO(b""), "")},
                    content_type="multipart/form-data",
                )
                self.assertEqual(response.status_code, 200)
            vision_limited = admin.post(
                "/pets/find-similar",
                data={
                    "csrf_token": admin_image_token,
                    "photo": (BytesIO(b""), ""),
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(vision_limited.status_code, 429)
        finally:
            self.app.config.update(previous_values)
            clear_test_keys()

    def test_demo_catalog_images_and_sales_seed_are_rich_and_repeatable(self):
        seed_database()

        def snapshot():
            with get_connection() as connection:
                product_codes = tuple(item[0] for item in PRODUCTS)
                customer_phones = tuple(item[1] for item in CUSTOMERS)
                pet_codes = tuple(item[0] for item in PETS)
                product_marks = ",".join(["%s"] * len(product_codes))
                customer_marks = ",".join(["%s"] * len(customer_phones))
                pet_marks = ",".join(["%s"] * len(pet_codes))
                products = fetch_one(
                    connection,
                    f"SELECT COUNT(*) total, COALESCE(SUM(stock_qty), 0) stock, "
                    f"SUM(photo_filename IS NOT NULL) photos FROM products WHERE code IN ({product_marks})",
                    product_codes,
                )
                customers = fetch_one(
                    connection,
                    f"SELECT COUNT(*) total FROM customers WHERE phone IN ({customer_marks})",
                    customer_phones,
                )["total"]
                pets = fetch_one(
                    connection,
                    f"SELECT COUNT(*) total, SUM(photo_filename IS NOT NULL) photos "
                    f"FROM pets WHERE code IN ({pet_marks})",
                    pet_codes,
                )
                sales = fetch_one(
                    connection,
                    "SELECT COUNT(*) total FROM invoices WHERE note LIKE '[DEMO] DEMO-SALE-%'",
                )["total"]
                return products, customers, pets, sales

        first = snapshot()
        seed_database()
        second = snapshot()
        self.assertEqual(first, second)
        products, customers, pets, sales = second
        self.assertEqual(products["total"], len(PRODUCTS))
        self.assertGreaterEqual(products["stock"], 200)
        self.assertEqual(customers, len(CUSTOMERS))
        self.assertEqual(pets["total"], len(PETS))
        self.assertGreaterEqual(pets["photos"], 3)
        self.assertEqual(sales, len(DEMO_SALES))

    def test_invoice_detail_and_payment_route_work(self):
        client = self._login("admin", "Admin@123")
        with get_connection() as connection:
            user = fetch_one(connection, "SELECT id FROM users WHERE username = 'admin'")
            customer = fetch_one(connection, "SELECT id FROM customers WHERE active = 1 ORDER BY id LIMIT 1")
            product = fetch_one(connection, "SELECT id, stock_qty FROM products WHERE active = 1 ORDER BY id LIMIT 1")
            stock_before = product["stock_qty"]
        invoice_id = invoice_service.create_invoice(
            user["id"],
            {"customer_id": str(customer["id"]), "note": ""},
            [{"item_type": "product", "item_id": str(product["id"]), "quantity": "1"}],
        )
        try:
            response = client.get(f"/invoices/{invoice_id}")
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            self.assertIn("Thức ăn cho mèo 1kg", html)
            self.assertIn("100.000\u00a0VND", html)
            self.assertIn("Xác nhận thanh toán", html)
            token = re.search(r'name="csrf_token" value="([^"]+)"', html)
            self.assertIsNotNone(token)
            payment = client.post(
                f"/invoices/{invoice_id}/pay",
                data={"csrf_token": token.group(1)},
            )
            self.assertEqual(payment.status_code, 302)
            paid_page = client.get(f"/invoices/{invoice_id}")
            self.assertEqual(paid_page.status_code, 200)
            self.assertIn("Đã thanh toán", paid_page.get_data(as_text=True))
            with get_connection() as connection:
                updated_product = fetch_one(
                    connection,
                    "SELECT stock_qty FROM products WHERE id = %s",
                    (product["id"],),
                )
                audit_count = fetch_one(
                    connection,
                    "SELECT COUNT(*) total FROM audit_events WHERE entity_type = 'invoice' "
                    "AND entity_id = %s AND event_type IN ('invoice.created', 'invoice.paid')",
                    (invoice_id,),
                )["total"]
            self.assertEqual(updated_product["stock_qty"], stock_before - 1)
            self.assertEqual(audit_count, 2)
        finally:
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "DELETE FROM audit_events WHERE entity_type = 'invoice' AND entity_id = %s",
                        (invoice_id,),
                    )
                    cursor.execute("DELETE FROM stock_movements WHERE invoice_id = %s", (invoice_id,))
                    cursor.execute(
                        "UPDATE products SET stock_qty = %s WHERE id = %s",
                        (stock_before, product["id"]),
                    )
                    cursor.execute("DELETE FROM invoice_items WHERE invoice_id = %s", (invoice_id,))
                    cursor.execute("DELETE FROM invoices WHERE id = %s", (invoice_id,))
                    connection.commit()
                finally:
                    cursor.close()

    def test_stock_adjustment_is_recorded_atomically(self):
        client = self._login("admin", "Admin@123")
        with get_connection() as connection:
            actor = fetch_one(connection, "SELECT id FROM users WHERE username = 'admin'")
        product_code = f"AUD-{uuid4().hex[:8].upper()}"
        product_id = product_service.create_product(
            actor["id"],
            {
                "code": product_code,
                "name": "Sản phẩm kiểm tra nhật ký",
                "category": "Kiểm thử",
                "description": "",
                "unit_price": "1",
                "stock_qty": "5",
                "reorder_level": "0",
            },
        )
        product_service.adjust_stock(
            actor["id"], product_id, {"quantity_delta": "1", "reason": "Kiểm thử audit"}
        )
        try:
            page = client.get("/activity/")
            self.assertEqual(page.status_code, 200)
            self.assertIn("Điều chỉnh tồn kho", page.get_data(as_text=True))
            with get_connection() as connection:
                event = fetch_one(
                    connection,
                    "SELECT event_type FROM audit_events WHERE entity_type = 'product' "
                    "AND entity_id = %s AND event_type = 'stock.adjusted' ORDER BY id DESC LIMIT 1",
                    (product_id,),
                )
            self.assertEqual(event["event_type"], "stock.adjusted")
        finally:
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "DELETE FROM audit_events WHERE entity_type = 'product' AND entity_id = %s "
                        "AND event_type = 'stock.adjusted'",
                        (product_id,),
                    )
                    cursor.execute(
                        "DELETE FROM stock_movements WHERE product_id = %s",
                        (product_id,),
                    )
                    cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
                    connection.commit()
                finally:
                    cursor.close()

    def test_invoice_lookup_endpoints_search_customer_and_saleable_items(self):
        client = self._login("admin", "Admin@123")
        page = client.get("/invoices/new")
        self.assertEqual(page.status_code, 200)
        self.assertIn("data-lookup-widget", page.get_data(as_text=True))

        customers = client.get("/invoices/lookups/customers?q=Kh%C3%A1ch%20demo%2001")
        self.assertEqual(customers.status_code, 200)
        customer_items = customers.get_json()["items"]
        self.assertEqual(len(customer_items), 1)
        self.assertIn("Khách demo 01", customer_items[0]["full_name"])

        items = client.get("/invoices/lookups/items?q=FOOD-001")
        self.assertEqual(items.status_code, 200)
        payload = items.get_json()
        self.assertEqual([item["code"] for item in payload["products"]], ["FOOD-001"])
        self.assertEqual(payload["pets"], [])

    def test_admin_create_forms_save_customer_product_and_pet(self):
        client = self._login("admin", "Admin@123")
        with get_connection() as connection:
            admin = fetch_one(
                connection,
                "SELECT id, preferred_locale FROM users WHERE username = 'admin'",
            )
        suffix = uuid4().hex[:8].upper()
        customer_name = f"Khách form {suffix}"
        phone = "09" + f"{uuid4().int % 100_000_000:08d}"
        product_code = f"TST-{suffix}"
        pet_code = f"PET-TST-{suffix}"
        product_photo_filename = None
        customer_path = "/customers/new"
        product_path = "/products/new"
        pet_path = "/pets/new"
        product_image = BytesIO()
        Image.new("RGB", (48, 48), (78, 142, 112)).save(product_image, format="PNG")
        try:
            response = client.post(
                customer_path,
                data={
                    "csrf_token": self._csrf_token(client, customer_path),
                    "full_name": customer_name,
                    "phone": phone,
                    "address": "",
                },
            )
            self.assertEqual(response.status_code, 302)
            response = client.post(
                product_path,
                data={
                    "csrf_token": self._csrf_token(client, product_path),
                    "code": product_code,
                    "name": f"Sản phẩm test {suffix}",
                    "category": "Test",
                    "description": "Mô tả hàng test.",
                    "unit_price": "75000",
                    "stock_qty": "3",
                    "reorder_level": "4",
                    "photo": (BytesIO(product_image.getvalue()), "product-test.png"),
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 302)
            slots = self.app.extensions["petcare_image_processing_slots"]
            configured_slots = self.app.config["IMAGE_PROCESSING_CONCURRENCY"]
            reacquired = sum(1 for _ in range(configured_slots) if slots.acquire(blocking=False))
            for _ in range(reacquired):
                slots.release()
            self.assertEqual(reacquired, configured_slots)
            with get_connection() as connection:
                product_row = fetch_one(
                    connection,
                    "SELECT id, photo_filename, description, reorder_level FROM products WHERE code = %s",
                    (product_code,),
                )
            self.assertIsNotNone(product_row["photo_filename"])
            product_photo_filename = product_row["photo_filename"]
            self.assertEqual(product_row["description"], "Mô tả hàng test.")
            self.assertEqual(product_row["reorder_level"], 4)
            product_photo = client.get(f"/products/photo/{product_photo_filename}")
            self.assertEqual(product_photo.status_code, 200)
            self.assertEqual(product_photo.mimetype, "image/jpeg")
            product_photo.close()
            edit_path = f"/products/{product_row['id']}/edit"
            update_response = client.post(
                edit_path,
                data={
                    "csrf_token": self._csrf_token(client, edit_path),
                    "code": product_code,
                    "name": f"Sản phẩm test {suffix}",
                    "category": "Test",
                    "description": "Mô tả hàng test đã chỉnh.",
                    "unit_price": "75000",
                    "reorder_level": "4",
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(update_response.status_code, 302)
            with get_connection() as connection:
                updated_product = fetch_one(
                    connection,
                    "SELECT photo_filename, description FROM products WHERE id = %s",
                    (product_row["id"],),
                )
            self.assertEqual(updated_product["photo_filename"], product_photo_filename)
            self.assertEqual(updated_product["description"], "Mô tả hàng test đã chỉnh.")
            retained_photo = client.get(f"/products/photo/{product_photo_filename}")
            self.assertEqual(retained_photo.status_code, 200)
            retained_photo.close()
            response = client.post(
                pet_path,
                data={
                    "csrf_token": self._csrf_token(client, pet_path),
                    "code": pet_code,
                    "name": f"Miu test {suffix}",
                    "species": "Mèo",
                    "breed": "",
                    "sex": "unknown",
                    "birth_date": "",
                    "weight_kg": "",
                    "coat_color": "",
                    "sale_price": "2000000",
                },
            )
            self.assertEqual(response.status_code, 302)
            self.assertIn(customer_name, client.get(f"/customers/?q={phone}").get_data(as_text=True))
            self.assertIn(product_code, client.get(f"/products/?q={product_code}").get_data(as_text=True))
            self.assertIn(pet_code, client.get(f"/pets/?q={pet_code}").get_data(as_text=True))
            activity = client.get("/activity/").get_data(as_text=True)
            self.assertIn("Thêm khách hàng", activity)
            self.assertIn("Thêm sản phẩm", activity)
            self.assertIn("Thêm thú cưng", activity)
            english_activity = client.post(
                "/language",
                data={
                    "csrf_token": self._csrf_token(client, "/activity/"),
                    "locale": "en",
                    "next": "/activity/",
                },
                follow_redirects=True,
            ).get_data(as_text=True)
            self.assertIn("Added customer", english_activity)
            self.assertIn("Added product", english_activity)
            self.assertIn("Added pet", english_activity)
        finally:
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE users SET preferred_locale = %s WHERE id = %s",
                        (admin["preferred_locale"], admin["id"]),
                    )
                    cursor.execute("SELECT id FROM products WHERE code = %s", (product_code,))
                    product = cursor.fetchone()
                    cursor.execute("SELECT id FROM pets WHERE code = %s", (pet_code,))
                    pet = cursor.fetchone()
                    cursor.execute("SELECT id FROM customers WHERE phone = %s", (phone,))
                    customer = cursor.fetchone()
                    for entity_type, row in (
                        ("product", product), ("pet", pet), ("customer", customer),
                    ):
                        if row:
                            cursor.execute(
                                "DELETE FROM audit_events WHERE entity_type = %s AND entity_id = %s",
                                (entity_type, row[0]),
                            )
                    cursor.execute("SELECT id FROM products WHERE code = %s", (product_code,))
                    product = cursor.fetchone()
                    if product:
                        cursor.execute("DELETE FROM stock_movements WHERE product_id = %s", (product[0],))
                        cursor.execute("DELETE FROM products WHERE id = %s", (product[0],))
                    cursor.execute("DELETE FROM pets WHERE code = %s", (pet_code,))
                    cursor.execute("DELETE FROM customers WHERE phone = %s", (phone,))
                    connection.commit()
                finally:
                    cursor.close()
            if product_photo_filename:
                from petcare.vision.photo_storage import remove_pet_photo

                remove_pet_photo(
                    product_photo_filename, self.app.config["PRODUCT_IMAGE_DIR"]
                )

    def test_concurrent_photo_replacements_leave_no_orphaned_image(self):
        with get_connection() as connection:
            admin = fetch_one(
                connection,
                "SELECT u.id, tu.tenant_id FROM users u "
                "JOIN tenant_users tu ON tu.user_id = u.id "
                "JOIN tenants t ON t.id = tu.tenant_id "
                "WHERE u.username = 'admin' AND t.slug = 'main'",
            )

        cases = (
            ("product", product_service, product_repo, "get_product", "PRODUCT_IMAGE_DIR"),
            ("pet", pet_service, pet_repo, "get_pet", "PET_IMAGE_DIR"),
        )
        for kind, service, repository, getter_name, config_key in cases:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as image_dir:
                previous_image_dir = self.app.config[config_key]
                self.app.config[config_key] = image_dir
                entity_id = None
                first_read = Event()
                second_attempt = Event()
                second_read = Event()
                release_first = Event()
                errors = []
                first_thread = None
                second_thread = None
                original_getter = getattr(repository, getter_name)
                suffix = uuid4().hex[:8].upper()

                if kind == "product":
                    create_data = {
                        "code": f"PHOTO-{suffix}", "name": "Photo race test",
                        "category": "Test", "description": "",
                        "unit_price": "10000", "stock_qty": "0", "reorder_level": "0",
                    }
                    update_data = {key: value for key, value in create_data.items() if key != "stock_qty"}
                    create_entity = service.create_product
                    update_entity = service.update_product
                    entity_table = "products"
                    entity_type = "product"
                else:
                    create_data = {
                        "code": f"PHOTO-{suffix}", "name": "Photo race test",
                        "species": "Mèo", "breed": "", "sex": "female",
                        "birth_date": "", "weight_kg": "", "coat_color": "",
                        "eye_color": "", "appearance_tags": "", "sale_price": "2000000",
                    }
                    update_data = create_data
                    create_entity = service.create_pet
                    update_entity = service.update_pet
                    entity_table = "pets"
                    entity_type = "pet"

                def upload(color):
                    output = BytesIO()
                    Image.new("RGB", (24, 24), color).save(output, format="PNG")
                    return FileStorage(
                        stream=BytesIO(output.getvalue()), filename="replacement.png"
                    )

                try:
                    with self.app.test_request_context("/"):
                        g.tenant = {"id": admin["tenant_id"]}
                        entity_id = create_entity(admin["id"], create_data)

                    def serialized_getter(connection, requested_id, lock=False):
                        if current_thread().name == f"{kind}-photo-first":
                            row = original_getter(connection, requested_id, lock=lock)
                            first_read.set()
                            if not release_first.wait(10):
                                raise TimeoutError("Timed out waiting to release the first photo update")
                            return row
                        if current_thread().name == f"{kind}-photo-second":
                            second_attempt.set()
                            row = original_getter(connection, requested_id, lock=lock)
                            second_read.set()
                            return row
                        return original_getter(connection, requested_id, lock=lock)

                    def update(color):
                        try:
                            with self.app.test_request_context("/"):
                                g.tenant = {"id": admin["tenant_id"]}
                                update_entity(admin["id"], entity_id, update_data, upload(color))
                        except Exception as exc:
                            errors.append(exc)

                    first_thread = Thread(
                        target=update, args=((54, 122, 190),), name=f"{kind}-photo-first"
                    )
                    second_thread = Thread(
                        target=update, args=((203, 112, 68),), name=f"{kind}-photo-second"
                    )
                    with patch.object(repository, getter_name, side_effect=serialized_getter):
                        first_thread.start()
                        self.assertTrue(first_read.wait(5))
                        second_thread.start()
                        self.assertTrue(second_attempt.wait(5))
                        self.assertFalse(second_read.wait(0.2), "second update must wait for the row lock")
                        release_first.set()
                        first_thread.join(15)
                        second_thread.join(15)
                    self.assertFalse(first_thread.is_alive())
                    self.assertFalse(second_thread.is_alive())
                    self.assertEqual(errors, [])

                    with get_connection() as connection:
                        row = fetch_one(
                            connection,
                            f"SELECT photo_filename FROM {entity_table} WHERE id = %s",
                            (entity_id,),
                        )
                    self.assertTrue(row["photo_filename"])
                    self.assertEqual(os.listdir(image_dir), [row["photo_filename"]])
                finally:
                    release_first.set()
                    try:
                        if first_thread and first_thread.is_alive():
                            first_thread.join(15)
                        if second_thread and second_thread.is_alive():
                            second_thread.join(15)
                        if entity_id:
                            with get_connection() as connection:
                                cursor = connection.cursor()
                                try:
                                    cursor.execute(
                                        "DELETE FROM audit_events WHERE tenant_id = %s "
                                        "AND entity_type = %s AND entity_id = %s",
                                        (admin["tenant_id"], entity_type, entity_id),
                                    )
                                    if kind == "product":
                                        cursor.execute(
                                            "DELETE FROM stock_movements WHERE product_id = %s", (entity_id,)
                                        )
                                    cursor.execute(
                                        f"DELETE FROM {entity_table} WHERE id = %s", (entity_id,)
                                    )
                                    connection.commit()
                                finally:
                                    cursor.close()
                    finally:
                        self.app.config[config_key] = previous_image_dir

    def test_image_upload_processing_saturation_redirects_with_retry_hint(self):
        client = self._login("admin", "Admin@123")
        csrf_token = self._csrf_token(client, "/pets/find-similar")
        slots = self.app.extensions["petcare_image_processing_slots"]
        configured_slots = self.app.config["IMAGE_PROCESSING_CONCURRENCY"]
        held_slots = 0
        image = BytesIO()
        Image.new("RGB", (8, 8), (100, 120, 140)).save(image, format="PNG")
        image.seek(0)
        try:
            for _ in range(configured_slots):
                if slots.acquire(blocking=False):
                    held_slots += 1
            self.assertEqual(held_slots, configured_slots)
            no_photo_response = client.post(
                "/products/new",
                data={"csrf_token": self._csrf_token(client, "/products/new")},
            )
            self.assertEqual(no_photo_response.status_code, 200)
            self.assertIsNone(no_photo_response.headers.get("Retry-After"))
            response = client.post(
                "/pets/find-similar",
                data={
                    "csrf_token": csrf_token,
                    "photo": (image, "saturation-test.png"),
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers.get("Retry-After"), "2")
            self.assertEqual(response.headers.get("Location"), "/pets/find-similar")
        finally:
            for _ in range(held_slots):
                slots.release()

        retry_page = client.get(response.headers["Location"])
        self.assertEqual(retry_page.status_code, 200)
        self.assertIn("Đang xử lý ảnh khác", retry_page.get_data(as_text=True))

    def test_catalog_image_upload_quota_is_shared_between_app_instances(self):
        client = self._login("admin", "Admin@123")
        with get_connection() as connection:
            admin = fetch_one(connection, "SELECT id FROM users WHERE username = 'admin'")
        identities = (
            ("catalog_image_upload", str(admin["id"])),
            ("catalog_image_upload_ip", "127.0.0.1"),
        )
        keys = [
            (
                scope,
                hmac.new(
                    self.app.config["SECRET_KEY"].encode("utf-8"),
                    f"api:{scope}:{identity}".encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest(),
            )
            for scope, identity in identities
        ]
        previous_values = {
            name: self.app.config[name]
            for name in (
                "CATALOG_IMAGE_UPLOAD_RATE_LIMIT_PER_MINUTE",
                "CATALOG_IMAGE_UPLOAD_IP_RATE_LIMIT_PER_MINUTE",
            )
        }

        def clear_test_keys():
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    for scope, key in keys:
                        cursor.execute(
                            "DELETE FROM request_throttle WHERE key_hash = %s AND scope = %s",
                            (key, scope),
                        )
                    connection.commit()
                finally:
                    cursor.close()

        clear_test_keys()
        try:
            self.app.config.update(
                CATALOG_IMAGE_UPLOAD_RATE_LIMIT_PER_MINUTE=100,
                CATALOG_IMAGE_UPLOAD_IP_RATE_LIMIT_PER_MINUTE=1,
            )
            second_app = create_app(self.app.config.copy())
            second_client = second_app.test_client()
            login_page = second_client.get("/login")
            login_token = re.search(
                r'name="csrf_token" value="([^"]+)"', login_page.get_data(as_text=True)
            )
            self.assertEqual(login_page.status_code, 200)
            self.assertIsNotNone(login_token)
            login_response = second_client.post(
                "/login",
                data={
                    "csrf_token": login_token.group(1),
                    "store_slug": "main",
                    "username": "admin",
                    "password": "Admin@123",
                },
            )
            self.assertEqual(login_response.status_code, 302)

            clients = (client, second_client)
            responses = []
            for upload_client in clients:
                token = self._csrf_token(upload_client, "/products/new")
                responses.append(upload_client.post(
                    "/products/new",
                    data={
                        "csrf_token": token,
                        "photo": (BytesIO(b"image upload quota probe"), "quota-probe.png"),
                    },
                    content_type="multipart/form-data",
                ))

            self.assertEqual(responses[0].status_code, 200)
            self.assertEqual(responses[1].status_code, 302)
            self.assertGreater(int(responses[1].headers.get("Retry-After", "0")), 0)
            self.assertEqual(responses[1].headers.get("Location"), "/products/new")
            retry_page = second_client.get(responses[1].headers["Location"])
            self.assertIn("tải lên nhiều ảnh", retry_page.get_data(as_text=True))

            clear_test_keys()
            self.app.config.update(
                CATALOG_IMAGE_UPLOAD_RATE_LIMIT_PER_MINUTE=1,
                CATALOG_IMAGE_UPLOAD_IP_RATE_LIMIT_PER_MINUTE=100,
            )
            account_token = self._csrf_token(client, "/products/new")
            account_limited_requests = []
            for _ in range(2):
                account_limited_requests.append(client.post(
                    "/products/new",
                    data={
                        "csrf_token": account_token,
                        "photo": (BytesIO(b"image account quota probe"), "quota-probe.png"),
                    },
                    content_type="multipart/form-data",
                ))
            self.assertEqual(account_limited_requests[0].status_code, 200)
            self.assertEqual(account_limited_requests[1].status_code, 302)
            self.assertGreater(
                int(account_limited_requests[1].headers.get("Retry-After", "0")), 0
            )
        finally:
            self.app.config.update(previous_values)
            clear_test_keys()

    def test_pet_photo_upload_and_visual_search_use_mysql_profile(self):
        client = self._login("admin", "Admin@123")
        search_page = client.get("/pets/find-similar")
        self.assertEqual(search_page.status_code, 200)
        search_html = search_page.get_data(as_text=True)
        self.assertIn('capture="environment"', search_html)
        self.assertIn("Bật camera máy tính", search_html)
        self.assertIn("camera_scan.js", search_html)
        self.assertIn("ảnh được gửi tới máy chủ ứng dụng để xử lý", search_html)
        self.assertIn("không được lưu thành hồ sơ", search_html)
        self.assertNotIn("data:image/png;base64,", search_html)

        # LAN sharing is opt-in and renders a local QR only when configured.
        self.app.config.update(
            LAN_ACCESS_ENABLED=True,
            LAN_ACCESS_BASE_URL="http://192.168.1.25:5000",
        )
        try:
            phone_page = client.get("/pets/find-similar")
            self.assertEqual(phone_page.status_code, 200)
            phone_html = phone_page.get_data(as_text=True)
            self.assertIn("DÙNG CAMERA ĐIỆN THOẠI", phone_html)
            self.assertIn("data:image/png;base64,", phone_html)
        finally:
            self.app.config.update(LAN_ACCESS_ENABLED=False, LAN_ACCESS_BASE_URL="")

        pet_code = f"PET-IMG-{uuid4().hex[:8].upper()}"
        output = BytesIO()
        Image.new("RGB", (96, 96), (218, 178, 82)).save(output, format="PNG")
        image_bytes = output.getvalue()
        photo_filename = None
        try:
            response = client.post(
                "/pets/new",
                data={
                    "csrf_token": self._csrf_token(client, "/pets/new"),
                    "code": pet_code,
                    "name": "Miu ảnh test",
                    "species": "Mèo",
                    "breed": "Mèo ta",
                    "sex": "unknown",
                    "birth_date": "",
                    "weight_kg": "",
                    "coat_color": "vàng",
                    "eye_color": "xanh lá",
                    "appearance_tags": "lông ngắn, dáng nhỏ",
                    "sale_price": "2000000",
                    "photo": (BytesIO(image_bytes), "miu.png"),
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 302)
            with get_connection() as connection:
                pet = fetch_one(
                    connection,
                    "SELECT id, photo_filename, photo_descriptor FROM pets WHERE code = %s",
                    (pet_code,),
                )
            self.assertIsNotNone(pet)
            self.assertIsNotNone(pet["photo_filename"])
            self.assertIsNotNone(pet["photo_descriptor"])
            self.assertIn("center_color_histogram", json.loads(pet["photo_descriptor"]))
            self.assertEqual(len(json.loads(pet["photo_descriptor"])["visual_hash"]), 16)
            with get_connection() as connection:
                photo_index = fetch_one(
                    connection,
                    "SELECT COUNT(*) band_count FROM pet_photo_lsh "
                    "WHERE pet_id = %s",
                    (pet["id"],),
                )
            self.assertEqual(photo_index["band_count"], 8)
            photo_filename = pet["photo_filename"]

            # A pre-index photo remains searchable during rollout, then the
            # dry-run-first reindex rebuilds its hash and tenant-scoped bands.
            legacy_descriptor = json.loads(pet["photo_descriptor"])
            legacy_descriptor.pop("visual_hash")
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE pets SET photo_descriptor = %s WHERE id = %s",
                        (json.dumps(legacy_descriptor), pet["id"]),
                    )
                    cursor.execute("DELETE FROM pet_photo_lsh WHERE pet_id = %s", (pet["id"],))
                    connection.commit()
                finally:
                    cursor.close()
            reindexed = reindex_pet_descriptors(apply=True)
            self.assertEqual(reindexed["updated"], 1)
            with get_connection() as connection:
                photo_index = fetch_one(
                    connection,
                    "SELECT COUNT(*) band_count FROM pet_photo_lsh WHERE pet_id = %s",
                    (pet["id"],),
                )
            self.assertEqual(photo_index["band_count"], 8)

            response = client.post(
                "/pets/find-similar",
                data={
                    "csrf_token": self._csrf_token(client, "/pets/find-similar"),
                    "photo": (BytesIO(image_bytes), "query.png"),
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 200)
            result_html = response.get_data(as_text=True)
            self.assertIn(pet_code, result_html)
            self.assertIn("Gợi ý #1", result_html)
            self.assertIn("không phải phần trăm xác suất", result_html)
            self.assertIn("chỉ mục ảnh để chọn hồ sơ ứng viên", result_html)
            self.assertNotIn("% tương tự", result_html)
        finally:
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute("DELETE FROM pets WHERE code = %s", (pet_code,))
                    connection.commit()
                finally:
                    cursor.close()
            if photo_filename:
                from petcare.vision.photo_storage import remove_pet_photo

                from flask import current_app
                with self.app.app_context():
                    remove_pet_photo(photo_filename, current_app.config["PET_IMAGE_DIR"])

    def test_assistant_returns_current_shop_context_for_authenticated_user(self):
        client = self._login("admin", "Admin@123")
        token = self._csrf_token(client, "/dashboard")

        response = client.post(
            "/assistant/chat",
            json={"message": "Cho tôi biết danh sách sản phẩm"},
            headers={"X-CSRFToken": token},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["mode"], "local")
        self.assertIn("Thức ăn cho mèo 1kg", payload["reply"])

    def test_role_change_is_applied_to_an_existing_session(self):
        client = self._login("admin", "Admin@123")
        with get_connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "UPDATE tenant_users tu JOIN users u ON u.id = tu.user_id "
                    "SET tu.role = 'staff' WHERE u.username = 'admin' "
                    "AND tu.tenant_id = (SELECT id FROM tenants WHERE slug = 'main')"
                )
                connection.commit()
            finally:
                cursor.close()
        try:
            self.assertEqual(client.get("/users/").status_code, 403)
        finally:
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE tenant_users tu JOIN users u ON u.id = tu.user_id "
                        "SET tu.role = 'owner' WHERE u.username = 'admin' "
                        "AND tu.tenant_id = (SELECT id FROM tenants WHERE slug = 'main')"
                    )
                    connection.commit()
                finally:
                    cursor.close()

    def test_store_data_and_catalog_codes_are_isolated_per_tenant(self):
        suffix = uuid4().hex[:12]
        store_slug = "branch-" + suffix
        username = "branch_" + suffix
        password = "Branch@123"
        tenant_id, user_id = create_store(
            store_slug, "Branch " + suffix, username, "Branch Admin", password
        )
        with get_connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "INSERT INTO tenant_users (tenant_id, user_id, role, active) "
                    "SELECT id, %s, 'staff', 1 FROM tenants WHERE slug = 'main'",
                    (user_id,),
                )
                cursor.execute(
                    "INSERT INTO products "
                    "(tenant_id, code, name, category, unit_price, stock_qty) "
                    "VALUES (%s, 'FOOD-001', 'Sản phẩm cửa hàng riêng', 'Test', 1000, 2)",
                    (tenant_id,),
                )
                branch_product_id = cursor.lastrowid
                cursor.execute(
                    "SELECT id, name FROM products WHERE tenant_id = "
                    "(SELECT id FROM tenants WHERE slug = 'main') AND code = 'FOOD-001'"
                )
                main_product_id, main_product_name = cursor.fetchone()
                cursor.execute(
                    "SELECT id, full_name, active FROM customers WHERE tenant_id = "
                    "(SELECT id FROM tenants WHERE slug = 'main') AND active = 1 "
                    "ORDER BY id LIMIT 1"
                )
                main_customer = cursor.fetchone()
                main_customer_id, main_customer_name, main_customer_active = main_customer
                cursor.execute(
                    "SELECT id, name, photo_filename FROM pets WHERE tenant_id = "
                    "(SELECT id FROM tenants WHERE slug = 'main') "
                    "AND sale_status = 'available' AND photo_filename IS NOT NULL "
                    "ORDER BY id LIMIT 1"
                )
                main_pet_id, main_pet_name, main_pet_photo = cursor.fetchone()
                cursor.execute(
                    "SELECT id FROM invoices WHERE tenant_id = "
                    "(SELECT id FROM tenants WHERE slug = 'main') ORDER BY id LIMIT 1"
                )
                main_invoice_id = cursor.fetchone()[0]
                connection.commit()
            finally:
                cursor.close()

        second_tenant_id = None
        try:
            second_slug = "branch-two-" + suffix
            second_tenant_id, second_user_id = create_store(
                second_slug, "Second branch " + suffix, username, "Branch Admin", password
            )
            self.assertEqual(second_user_id, user_id)
            with self.assertRaises(ValueError):
                create_store(
                    "invalid-" + suffix, "Invalid branch", username,
                    "Branch Admin", "Wrong@123",
                )
            branch = self._login(username, password, store_slug)
            self.assertIn("Chuyển cửa hàng", branch.get("/dashboard").get_data(as_text=True))
            page = branch.get("/products/")
            html = page.get_data(as_text=True)
            self.assertEqual(page.status_code, 200)
            self.assertIn("Sản phẩm cửa hàng riêng", html)
            self.assertNotIn("Thức ăn cho mèo 1kg", html)
            self.assertEqual(branch.get(f"/products/{main_product_id}/edit").status_code, 302)
            self.assertEqual(branch.get(f"/pets/photo/{main_pet_photo}").status_code, 404)
            customer_page = branch.get("/customers/")
            self.assertEqual(customer_page.status_code, 200)
            self.assertNotIn(main_customer_name, customer_page.get_data(as_text=True))
            self.assertEqual(branch.get(f"/customers/{main_customer_id}/edit").status_code, 302)
            pet_page = branch.get("/pets/")
            self.assertEqual(pet_page.status_code, 200)
            self.assertNotIn(main_pet_name, pet_page.get_data(as_text=True))
            self.assertEqual(branch.get(f"/pets/{main_pet_id}").status_code, 302)
            self.assertEqual(branch.get(f"/invoices/{main_invoice_id}").status_code, 302)
            customer_lookup = branch.get(
                "/invoices/lookups/customers", query_string={"q": main_customer_name}
            )
            self.assertEqual(customer_lookup.status_code, 200)
            self.assertEqual(customer_lookup.get_json()["items"], [])
            product_lookup = branch.get(
                "/invoices/lookups/items", query_string={"q": main_product_name}
            )
            self.assertEqual(product_lookup.status_code, 200)
            self.assertEqual(product_lookup.get_json()["products"], [])
            pet_lookup = branch.get(
                "/invoices/lookups/items", query_string={"q": main_pet_name}
            )
            self.assertEqual(pet_lookup.status_code, 200)
            self.assertEqual(pet_lookup.get_json()["pets"], [])

            # A valid tenant admin must not be able to change another store's
            # record by guessing an integer ID from that store.
            response = branch.post(
                f"/customers/{main_customer_id}/deactivate",
                data={"csrf_token": self._csrf_token(branch, "/customers/")},
            )
            self.assertEqual(response.status_code, 302)
            with get_connection() as connection:
                remaining_customer = fetch_one(
                    connection,
                    "SELECT active FROM customers WHERE id = %s AND tenant_id = "
                    "(SELECT id FROM tenants WHERE slug = 'main')",
                    (main_customer_id,),
                )
            self.assertEqual(remaining_customer["active"], main_customer_active)
            with self.assertRaises(ValidationError):
                with self.app.test_request_context("/"):
                    g.tenant = {"id": tenant_id}
                    invoice_service.create_invoice(
                        user_id,
                        {"customer_id": str(main_customer_id), "note": "cross-store"},
                        [{"item_type": "product", "item_id": str(main_product_id), "quantity": "1"}],
                    )
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    with self.assertRaises(IntegrityError):
                        cursor.execute(
                            "INSERT INTO invoices (tenant_id, customer_id, created_by) "
                            "VALUES (%s, %s, %s)",
                            (tenant_id, main_customer_id, user_id),
                        )
                    connection.rollback()
                finally:
                    cursor.close()
            token = self._csrf_token(branch, "/dashboard")
            response = branch.post(
                "/stores/switch",
                data={"csrf_token": token, "store_slug": "main"},
            )
            self.assertEqual(response.status_code, 302)
            main_store_page = branch.get("/products/").get_data(as_text=True)
            self.assertIn("Thức ăn cho mèo 1kg", main_store_page)
            self.assertNotIn("Sản phẩm cửa hàng riêng", main_store_page)
            self.assertEqual(branch.get("/users/").status_code, 403)
            token = self._csrf_token(branch, "/dashboard")
            response = branch.post(
                "/stores/switch",
                data={"csrf_token": token, "store_slug": second_slug},
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(branch.get("/users/").status_code, 200)
            second_store_page = branch.get("/products/").get_data(as_text=True)
            self.assertNotIn("Sản phẩm cửa hàng riêng", second_store_page)
            self.assertNotIn("Thức ăn cho mèo 1kg", second_store_page)

            profile_page = branch.get("/account/settings")
            self.assertEqual(profile_page.status_code, 200)
            profile_update = branch.post(
                "/account/profile",
                data={
                    "csrf_token": self._csrf_token(branch, "/account/settings"),
                    "full_name": "Shared Branch Identity",
                    "current_password": password,
                },
            )
            self.assertEqual(profile_update.status_code, 302)
            with get_connection() as connection:
                profile_audit_count = fetch_one(
                    connection,
                    "SELECT COUNT(DISTINCT tenant_id) count FROM audit_events "
                    "WHERE actor_user_id = %s AND event_type = 'account.profile_updated' "
                    "AND tenant_id IN (%s, %s, (SELECT id FROM tenants WHERE slug = 'main'))",
                    (user_id, tenant_id, second_tenant_id),
                )["count"]
                shared_name = fetch_one(
                    connection, "SELECT full_name FROM users WHERE id = %s", (user_id,)
                )["full_name"]
            self.assertEqual(profile_audit_count, 3)
            self.assertEqual(shared_name, "Shared Branch Identity")

            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE tenant_users SET active = 0 WHERE user_id = %s "
                        "AND tenant_id IN (%s, %s)",
                        (user_id, tenant_id, second_tenant_id),
                    )
                    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
                    admin_id = cursor.fetchone()[0]
                    cursor.execute("SELECT id FROM tenants WHERE slug = 'main'")
                    main_tenant_id = cursor.fetchone()[0]
                    cursor.execute(
                        "SELECT COUNT(*) FROM tenant_users WHERE user_id = %s",
                        (user_id,),
                    )
                    self.assertEqual(cursor.fetchone()[0], 3)
                    connection.commit()
                finally:
                    cursor.close()

            with self.app.test_request_context("/"):
                g.tenant = {"id": main_tenant_id}
                with self.assertRaises(ForbiddenError):
                    auth_service.update_user(
                        admin_id, user_id,
                        {"full_name": "Changed across stores", "role": "staff", "active": "1", "password": ""},
                    )
                with self.assertRaises(ForbiddenError):
                    auth_service.update_user(
                        admin_id, user_id,
                        {"full_name": "Shared Branch Identity", "role": "staff", "active": "1", "password": "Changed@123"},
                    )
        finally:
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute("DELETE FROM audit_events WHERE actor_user_id = %s", (user_id,))
                    cursor.execute("DELETE FROM products WHERE id = %s AND tenant_id = %s", (branch_product_id, tenant_id))
                    cursor.execute(
                        "UPDATE customers SET active = %s WHERE id = %s AND tenant_id = "
                        "(SELECT id FROM tenants WHERE slug = 'main')",
                        (main_customer_active, main_customer_id),
                    )
                    cursor.execute("DELETE FROM tenant_users WHERE user_id = %s", (user_id,))
                    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                    cursor.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
                    if second_tenant_id:
                        cursor.execute("DELETE FROM tenants WHERE id = %s", (second_tenant_id,))
                    connection.commit()
                finally:
                    cursor.close()

    def test_locked_account_is_logged_out_on_next_request(self):
        client = self._login("admin", "Admin@123")
        with get_connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "UPDATE users SET active = 0 WHERE username = 'admin'"
                )
                connection.commit()
            finally:
                cursor.close()
        try:
            response = client.get("/dashboard")
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login", response.headers["Location"])
        finally:
            with get_connection() as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE users SET active = 1 WHERE username = 'admin'"
                    )
                    connection.commit()
                finally:
                    cursor.close()


if __name__ == "__main__":
    unittest.main()

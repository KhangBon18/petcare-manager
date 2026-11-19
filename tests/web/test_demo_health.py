from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import MagicMock, patch
from petcare import create_app
from petcare.routes.health_routes import demo_database_signature


class DemoHealthTests(TestCase):
    def test_local_signature_preserves_json_contract_and_is_not_exposed_remotely_or_in_production(
        self,
    ):
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "preflight-web-key",
                "APP_ENV": "test",
                "DB_NAME": "demo_test",
            }
        )

        @contextmanager
        def connection():
            yield MagicMock()

        with patch("petcare.routes.health_routes.read_connection", connection), patch(
            "petcare.routes.health_routes.schema_contract_is_ready", return_value=True
        ):
            client = app.test_client()
            response = client.get("/readyz")
            self.assertEqual(response.get_json(), {"status": "ready"})
            self.assertEqual(
                response.headers["X-PetCare-Demo-Database"],
                demo_database_signature(app.config),
            )
            remote = client.get(
                "/readyz", environ_overrides={"REMOTE_ADDR": "203.0.113.5"}
            )
            self.assertNotIn("X-PetCare-Demo-Database", remote.headers)
            app.config["APP_ENV"] = "production"
            self.assertNotIn("X-PetCare-Demo-Database", client.get("/readyz").headers)

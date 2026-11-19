from importlib import reload
import unittest
from unittest.mock import patch

from flask import jsonify, request

from petcare import create_app
from petcare.config import Config


class ProxyFixTests(unittest.TestCase):
    @staticmethod
    def _add_proxy_probe(app):
        @app.get("/_test/proxy-context")
        def proxy_context():
            return jsonify(
                remote_addr=request.remote_addr,
                scheme=request.scheme,
                host=request.host,
            )

    def _assert_proxy_boundary(self, app):
        self._add_proxy_probe(app)
        response = app.test_client().get(
            "/_test/proxy-context",
            base_url="http://petcare.internal:8000",
            headers={
                "X-Forwarded-For": "198.51.100.27",
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "attacker.example",
                "X-Forwarded-Port": "9443",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "remote_addr": "198.51.100.27",
                "scheme": "https",
                "host": "petcare.internal:8000",
            },
        )

    def test_trusts_only_forwarded_client_ip_and_scheme(self):
        app = create_app({
            "TESTING": True,
            "SECRET_KEY": "proxy-test-secret",
            "TRUST_PROXY": True,
        })
        self._assert_proxy_boundary(app)

    def test_production_wsgi_entrypoint_keeps_forwarded_host_and_port_untrusted(self):
        import wsgi

        with patch.object(Config, "TRUST_PROXY", True):
            app = reload(wsgi).app

        self._assert_proxy_boundary(app)


if __name__ == "__main__":
    unittest.main()

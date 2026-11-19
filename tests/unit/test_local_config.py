import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch


class LocalPortRegressionTests(unittest.TestCase):
    def config(self, environment):
        source = Path(__file__).resolve().parents[2] / "petcare" / "config.py"
        spec = importlib.util.spec_from_file_location("isolated_config_test", source)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, environment, clear=True), patch("dotenv.load_dotenv"):
            spec.loader.exec_module(module)
        return module.Config

    def test_local_default_avoids_airplay_and_uses_matching_public_origin(self):
        config = self.config({})
        self.assertEqual(config.APP_PORT, 5055)
        self.assertEqual(config.PUBLIC_BASE_URL, "http://127.0.0.1:5055")

    def test_explicit_local_port_and_public_origin_remain_configurable(self):
        config = self.config({"APP_PORT": "5050"})
        self.assertEqual(config.PUBLIC_BASE_URL, "http://127.0.0.1:5050")
        config = self.config({"APP_PORT": "5050", "PUBLIC_BASE_URL": "https://shop.example.test"})
        self.assertEqual(config.PUBLIC_BASE_URL, "https://shop.example.test")

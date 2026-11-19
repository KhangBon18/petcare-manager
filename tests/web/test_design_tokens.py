import unittest
from pathlib import Path

from petcare import create_app


class DesignTokenTests(unittest.TestCase):
    def test_base_loads_shared_tokens_before_component_styles(self):
        app = create_app({"TESTING": True, "SECRET_KEY": "design-token-tests-only"})
        html = app.test_client().get("/login").get_data(as_text=True)

        token_link = html.index("/static/css/tokens.css")
        component_link = html.index("/static/css/app.css")
        self.assertLess(token_link, component_link)

    def test_repeated_border_and_heading_colors_use_semantic_tokens(self):
        root = Path(__file__).resolve().parents[2]
        tokens = (root / "petcare/static/css/tokens.css").read_text()
        components = (root / "petcare/static/css/app.css").read_text()

        self.assertIn("--color-border-subtle: #edf1ee", tokens)
        self.assertIn("--color-ink-strong: #34463f", tokens)
        self.assertIn("--color-focus-ring: rgba(40, 122, 98, .35)", tokens)
        self.assertIn("--color-border-danger: #efd9d5", tokens)
        self.assertNotIn("#edf1ee", components.lower())
        self.assertNotIn("#34463f", components.lower())
        self.assertNotIn("#efd9d5", components.lower())
        self.assertIn("var(--color-border-subtle)", components)
        self.assertIn("var(--color-ink-strong)", components)
        self.assertIn("var(--color-focus-ring)", components)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

from petcare import create_app


class DesignTokenTests(unittest.TestCase):
    def test_base_loads_shared_tokens_before_component_styles(self):
        app = create_app({"TESTING": True, "SECRET_KEY": "design-token-tests-only"})
        html = app.test_client().get("/login").get_data(as_text=True)

        shared_link = html.index("/static/css/shared_tokens.css")
        token_link = html.index("/static/css/tokens.css")
        component_link = html.index("/static/css/app.css")
        ui_link = html.index("/static/css/ui.css")
        self.assertLess(shared_link, token_link)
        self.assertLess(token_link, component_link)
        self.assertLess(component_link, ui_link)

    def test_repeated_border_and_heading_colors_use_semantic_tokens(self):
        root = Path(__file__).resolve().parents[2]
        shared = (root / "petcare/static/css/shared_tokens.css").read_text()
        tokens = (root / "petcare/static/css/tokens.css").read_text()
        components = (root / "petcare/static/css/app.css").read_text()

        # Legacy Spruce & Saffron definitions must not reappear in authoritative tokens.css.
        for legacy_token in (
            "--primitive-spruce-",
            "--primitive-saffron-",
            "--primitive-forest-",
            "#1d6a53",
            "#11291f",
            "#edf1ee",
            "#34463f",
            "rgba(40, 122, 98",
            "#efd9d5",
            "#eeb04a",
        ):
            self.assertNotIn(legacy_token, tokens.lower())

        self.assertIn("--color-brand: var(--pc-brand)", tokens)
        self.assertIn("--color-border-subtle: var(--pc-surface-subtle)", tokens)
        self.assertIn("--color-ink-strong: var(--pc-ink-strong)", tokens)
        self.assertIn("--color-focus-ring: var(--pc-focus-ring)", tokens)
        self.assertIn("--color-border-danger: var(--pc-danger-border)", tokens)
        self.assertIn("--pc-surface-subtle: #F1F5F9;", shared)
        self.assertIn("--pc-ink-strong: #1E293B;", shared)
        self.assertIn("--pc-danger-border: #FECACA;", shared)

        self.assertNotIn("#edf1ee", components.lower())
        self.assertNotIn("#34463f", components.lower())
        self.assertNotIn("#efd9d5", components.lower())
        self.assertIn("var(--color-border-subtle)", components)
        self.assertIn("var(--color-ink-strong)", components)
        self.assertIn("var(--color-focus-ring)", components)

    def test_shared_precision_cloud_tokens_load_across_saas_and_storefront(self):
        root = Path(__file__).resolve().parents[2]
        shared = (root / "petcare/static/css/shared_tokens.css").read_text()
        storefront_css = (root / "petcare/static/css/storefront.css").read_text()
        tokens_css = (root / "petcare/static/css/tokens.css").read_text()

        self.assertIn("--pc-brand: #2563EB;", shared)
        self.assertIn("--pc-canvas: #F8FAFC;", shared)
        self.assertIn("--pc-tap-min: 44px;", shared)
        self.assertIn("--radius-lg: 10px;", tokens_css)
        self.assertIn("--sf-radius-lg: 18px;", storefront_css)

        app = create_app({"TESTING": True, "SECRET_KEY": "design-token-tests-only"})
        login_html = app.test_client().get("/login").get_data(as_text=True)
        self.assertLess(
            login_html.index("/static/css/shared_tokens.css"),
            login_html.index("/static/css/ui.css"),
        )


if __name__ == "__main__":
    unittest.main()

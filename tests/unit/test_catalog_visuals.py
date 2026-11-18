from pathlib import Path
from unittest import TestCase

from petcare import create_app
from petcare.services.catalog_visuals import pet_visual, product_visual


class CatalogVisualsTests(TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "catalog-visuals-secret"})
        self.ctx = self.app.test_request_context("/")
        self.ctx.push()
        self.static_root = Path(self.app.static_folder)

    def tearDown(self):
        self.ctx.pop()

    def test_stored_photo_takes_precedence_and_is_not_illustrative(self):
        prod = product_visual({"code": "FOOD-001", "category": "Thức ăn", "photo_filename": "abc.jpg"})
        self.assertEqual(prod["url"], "/products/photo/abc.jpg")
        self.assertEqual(prod["source"], "verified_uploaded_photo")
        self.assertFalse(prod["is_illustrative"])
        self.assertEqual(prod["fallback_url"], "/static/img/catalog/fallbacks/product-food.svg")

        pet = pet_visual({"code": "PET-005", "species": "Chó", "photo_filename": "t1-real.jpg"})
        self.assertEqual(pet["url"], "/pets/photo/t1-real.jpg")
        self.assertEqual(pet["source"], "verified_stored_photo")
        self.assertFalse(pet["is_illustrative"])
        self.assertEqual(pet["fallback_url"], "/static/img/catalog/fallbacks/pet-dog.svg")

    def test_all_demo_products_and_illustrative_pets_have_static_webp_assets(self):
        product_codes = (
            [f"FOOD-00{i}" for i in range(1, 9)]
            + [f"CARE-00{i}" for i in range(1, 6)]
            + [f"ACC-00{i}" for i in range(1, 10)]
        )
        for code in product_codes:
            vis = product_visual({"code": code, "category": ""})
            self.assertTrue(vis["is_illustrative"])
            self.assertEqual(vis["source"], "ai_generated_demo_illustration")
            rel = vis["url"].removeprefix("/static/")
            self.assertTrue((self.static_root / rel).is_file(), f"Missing {rel}")

        for code in [f"PET-00{i}" for i in range(5, 10)] + ["PET-010"]:
            vis = pet_visual({"code": code, "species": "Mèo"})
            self.assertTrue(vis["is_illustrative"])
            self.assertEqual(vis["source"], "ai_generated_demo_illustration")
            rel = vis["url"].removeprefix("/static/")
            self.assertTrue((self.static_root / rel).is_file(), f"Missing {rel}")

    def test_unknown_codes_fall_back_to_existing_svg_placeholders(self):
        for cat, expected in [
            ("Đồ chơi", "product-toy.svg"),
            ("Thức ăn", "product-food.svg"),
            ("Chăm sóc", "product-care.svg"),
            ("Phụ kiện", "product-acc.svg"),
            ("Khác", "product-generic.svg"),
        ]:
            vis = product_visual({"code": "../../etc/passwd", "category": cat})
            self.assertEqual(vis["source"], "ui_fallback")
            self.assertTrue(vis["is_illustrative"])
            self.assertTrue(vis["url"].endswith(f"/{expected}"))
            self.assertTrue((self.static_root / vis["url"].removeprefix("/static/")).is_file())

        for species, expected in [
            ("Mèo", "pet-cat.svg"),
            ("Chó", "pet-dog.svg"),
            ("Thỏ", "pet-rabbit.svg"),
            ("Hamster Bear", "pet-hamster.svg"),
            ("Chim cảnh", "pet-generic.svg"),
        ]:
            vis = pet_visual({"code": "PET-999", "species": species})
            self.assertEqual(vis["source"], "ui_fallback")
            self.assertTrue(vis["is_illustrative"])
            self.assertTrue(vis["url"].endswith(f"/{expected}"))
            self.assertTrue((self.static_root / vis["url"].removeprefix("/static/")).is_file())


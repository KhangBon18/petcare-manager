"""Pure presentation helper for catalog product and illustrative demo pet visuals.

This module never modifies database state and never mixes illustrative
portraits into AI-4.0 verified photo galleries or similarity search descriptors.
"""

from __future__ import annotations

import re
from pathlib import Path
from flask import url_for

_STATIC_ROOT = Path(__file__).resolve().parent.parent / "static"
_PRODUCT_DIR = _STATIC_ROOT / "img" / "catalog" / "products"
_PET_DIR = _STATIC_ROOT / "img" / "catalog" / "pets"

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _get(item, key: str, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _code_slug(code: str | None) -> str:
    if not code:
        return ""
    return _SLUG_RE.sub("-", str(code).strip().lower()).strip("-")


def _product_fallback_filename(item) -> str:
    code = str(_get(item, "code", "") or "").upper()
    category = str(_get(item, "category", "") or "").lower()
    if code == "ACC-007" or "đồ chơi" in category or "toy" in category:
        return "img/catalog/fallbacks/product-toy.svg"
    if code.startswith("FOOD-") or "thức ăn" in category or "food" in category:
        return "img/catalog/fallbacks/product-food.svg"
    if code.startswith("CARE-") or code == "ACC-009" or "chăm sóc" in category or "care" in category:
        return "img/catalog/fallbacks/product-care.svg"
    if code.startswith("ACC-") or "phụ kiện" in category or "accessor" in category:
        return "img/catalog/fallbacks/product-acc.svg"
    return "img/catalog/fallbacks/product-generic.svg"


def _pet_fallback_filename(item) -> str:
    species = str(_get(item, "species", "") or "").strip().lower()
    if species in {"mèo", "cat"}:
        return "img/catalog/fallbacks/pet-cat.svg"
    if species in {"chó", "dog"}:
        return "img/catalog/fallbacks/pet-dog.svg"
    if species in {"thỏ", "rabbit"}:
        return "img/catalog/fallbacks/pet-rabbit.svg"
    if "hamster" in species:
        return "img/catalog/fallbacks/pet-hamster.svg"
    return "img/catalog/fallbacks/pet-generic.svg"


def product_visual(item, public: bool = False) -> dict:
    """Resolve the display URL, resilient fallback URL, and provenance for a product."""
    fallback_rel = _product_fallback_filename(item)
    fallback_url = url_for("static", filename=fallback_rel)
    photo_filename = _get(item, "photo_filename")
    if photo_filename:
        endpoint = "storefront.public_product_photo" if public else "products.photo"
        return {
            "url": url_for(endpoint, filename=photo_filename),
            "fallback_url": fallback_url,
            "source": "verified_uploaded_photo",
            "is_illustrative": False,
        }
    slug = _code_slug(_get(item, "code"))
    if slug and (_PRODUCT_DIR / f"{slug}.webp").is_file():
        return {
            "url": url_for("static", filename=f"img/catalog/products/{slug}.webp"),
            "fallback_url": fallback_url,
            "source": "ai_generated_demo_illustration",
            "is_illustrative": True,
        }
    return {
        "url": fallback_url,
        "fallback_url": fallback_url,
        "source": "ui_fallback",
        "is_illustrative": True,
    }


def pet_visual(item, public: bool = False) -> dict:
    """Resolve display URL and provenance for a pet portrait without fabricating ID data."""
    fallback_rel = _pet_fallback_filename(item)
    fallback_url = url_for("static", filename=fallback_rel)
    photo_filename = _get(item, "photo_filename")
    if photo_filename:
        endpoint = "storefront.public_pet_photo" if public else "pets.photo"
        return {
            "url": url_for(endpoint, filename=photo_filename),
            "fallback_url": fallback_url,
            "source": "verified_stored_photo",
            "is_illustrative": False,
        }
    slug = _code_slug(_get(item, "code"))
    if slug and (_PET_DIR / f"{slug}.webp").is_file():
        return {
            "url": url_for("static", filename=f"img/catalog/pets/{slug}.webp"),
            "fallback_url": fallback_url,
            "source": "ai_generated_demo_illustration",
            "is_illustrative": True,
        }
    return {
        "url": fallback_url,
        "fallback_url": fallback_url,
        "source": "ui_fallback",
        "is_illustrative": True,
    }


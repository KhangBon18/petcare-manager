"""Deterministic filters and database-backed assistant cards; no LLM-generated SQL."""

import re

from petcare.repositories import catalog_repo
from petcare.services.assistant_query import catalog_filters
from petcare.services.catalog_intent import (
    _PRODUCT_STOPWORDS,
    _normalize,
    _product_intent,
    pet_filter_spec,
)


def lookup(connection, question, intent):
    if intent == "pet":
        spec = pet_filter_spec(question)
        kind = "pet"
    else:
        query, prices = catalog_filters(_normalize(question))
        spec = {
            "terms": sorted(set(re.findall(r"[a-z0-9]+", query)) - _PRODUCT_STOPWORDS),
            "prices": prices,
            "low_stock": intent == "stock" and not _product_intent(query, question),
        }
        # Low-stock wording with an explicit product is still a low-stock query,
        # unless it asks for the remaining quantity of a named item.
        if any(word in query for word in ("sap het", "low", "restock", "nguong")):
            spec["low_stock"] = True
        kind = "product"
    total, rows = catalog_repo.search(connection, kind, spec)
    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "kind": kind,
                "code": row["code"],
                "name": row["name"],
                "price": str(row["sale_price"] if kind == "pet" else row["unit_price"]),
                "status": row.get("sale_status", "active"),
                "stock": 1 if kind == "pet" else row["stock_qty"],
                "photo_filename": row.get("photo_filename"),
            }
        )
    return {"kind": kind, "total": total, "items": items, "limit": 12}

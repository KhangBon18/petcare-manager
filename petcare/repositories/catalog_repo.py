"""Whitelisted SQL filters search the full tenant catalog before applying a display limit."""

from petcare.repositories.base import fetch_all, fetch_one


def _like(value):
    return "%" + value.replace("=", "==").replace("%", "=%").replace("_", "=_") + "%"


def search(connection, kind, spec, limit=12):
    if kind not in {"pet", "product"}:
        raise ValueError("Unsupported catalog")
    pet = kind == "pet"
    table, price = ("pets", "sale_price") if pet else ("products", "unit_price")
    where = [
        "tenant_id = @petcare_tenant_id",
        "sale_status = 'available'" if pet else "active = 1",
    ]
    params = []
    fields = (
        (
            "code",
            "name",
            "breed",
            "species",
            "coat_color",
            "eye_color",
            "appearance_tags",
        )
        if pet
        else ("code", "name", "category")
    )
    if pet:
        species = spec.get("species")
        if species:
            aliases = (
                ("mèo", "cat", "feline")
                if species == "cat"
                else ("chó", "dog", "canine")
            )
            where.append(
                "("
                + " OR ".join(
                    "species COLLATE utf8mb4_0900_ai_ci LIKE %s ESCAPE '='"
                    for _ in aliases
                )
                + ")"
            )
            params.extend(_like(alias) for alias in aliases)
        if spec.get("sex"):
            where.append("sex = %s")
            params.append(spec["sex"])
        for field, key in (("coat_color", "coat_colors"), ("eye_color", "eye_colors")):
            for aliases in spec.get(key, []):
                where.append(
                    "("
                    + " OR ".join(
                        field + " COLLATE utf8mb4_0900_ai_ci LIKE %s ESCAPE '='"
                        for _ in aliases
                    )
                    + ")"
                )
                params.extend(_like(alias) for alias in aliases)
    elif spec.get("low_stock"):
        where.append("stock_qty <= reorder_level")
    for constraint in spec.get("prices", []):
        if constraint.minimum is not None:
            where.append(price + (" >= %s" if constraint.include_minimum else " > %s"))
            params.append(constraint.minimum)
        if constraint.maximum is not None:
            where.append(price + (" <= %s" if constraint.include_maximum else " < %s"))
            params.append(constraint.maximum)
    for term in spec.get("terms", []):
        where.append(
            "("
            + " OR ".join(
                field + " COLLATE utf8mb4_0900_ai_ci LIKE %s ESCAPE '='"
                for field in fields
            )
            + ")"
        )
        params.extend(_like(term) for _ in fields)
    clause = " AND ".join(where)
    # B608 reviewed: table/columns/operators are closed code constants; every
    # user value is bound separately. Regression tests exercise hostile values.
    count_sql = "SELECT COUNT(*) total FROM " + table + " WHERE " + clause  # nosec B608
    rows_sql = (
        "SELECT * FROM " + table + " WHERE " + clause + " ORDER BY name, id LIMIT %s"  # nosec B608
    )
    total = fetch_one(connection, count_sql, tuple(params))["total"]
    rows = fetch_all(connection, rows_sql, (*params, limit))
    return total, rows

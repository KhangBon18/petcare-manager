# Store Settings & Public Storefront Policies Contract (`STORE_SETTINGS_POLICIES.md`)

Canonical schema, validation, security, and operational contract for `tenant_public_policies` (introduced in `v2.1` Sprint 2, stabilized for RC).

---

## 1. Non-Fabrication Principle
PetCare Manager **never** invents, defaults, or displays unverified store addresses, opening hours, COD fees, "free shipping" claims, confirmation SLAs, return rules, or support channels.

- When all 12 policy fields are empty (`has_any_policy == False`), `/store/settings` displays `Chưa cấu hình (đang hiện nhãn bản xem thử)` and `/shop/checkout` renders `.sf-policy-placeholder` (`[CHỜ CHỦ SHOP XÁC NHẬN · BẢN XEM THỬ]`).
- When configured fields exist, Storefront renders only populated fields, grouping primary checkout delivery/pickup commitments (COD terms/fees, confirmation SLA, pickup address) above the submit button and secondary details (hours, returns, cancellation, hotline, privacy summary/link) inside an accessible `<details class="sf-policy-details">` disclosure.

---

## 2. Authoritative Schema Contract (`tenant_public_policies`)
Defined in [`petcare/database/storefront.sql`](../petcare/database/storefront.sql) and tracked under migration `storefront_public_policies_v1` (`petcare/database/readiness.py` + `initialize.py`):

| Column | SQL Type | Nullability / Default | Validation Max Length |
|---|---|---|---|
| `tenant_id` | `BIGINT UNSIGNED PRIMARY KEY` | `NOT NULL` | Primary key (tenant scope) |
| `pickup_address` | `VARCHAR(300)` | `NOT NULL DEFAULT ''` | `300` |
| `opening_hours` | `VARCHAR(200)` | `NOT NULL DEFAULT ''` | `200` |
| `cod_service_area_fees` | `VARCHAR(400)` | `NOT NULL DEFAULT ''` | `400` |
| `order_confirmation_sla` | `VARCHAR(200)` | `NOT NULL DEFAULT ''` | `200` |
| `return_refund_policy` | `VARCHAR(600)` | `NOT NULL DEFAULT ''` | `600` |
| `cancellation_instructions` | `VARCHAR(400)` | `NOT NULL DEFAULT ''` | `400` |
| `pet_handover_policy` | `VARCHAR(600)` | `NOT NULL DEFAULT ''` | `600` |
| `support_hotline` | `VARCHAR(60)` | `NOT NULL DEFAULT ''` | `60` (`6–20` digits via `_HOTLINE_RE`) |
| `support_zalo` | `VARCHAR(160)` | `NOT NULL DEFAULT ''` | `160` (`http`/`https` URL or Zalo handle) |
| `support_email` | `VARCHAR(254)` | `NOT NULL DEFAULT ''` | `254` (normalized & syntax-checked) |
| `privacy_terms_url` | `VARCHAR(300)` | `NOT NULL DEFAULT ''` | `300` (strict `http`/`https` URL) |
| `privacy_terms_summary` | `VARCHAR(400)` | `NOT NULL DEFAULT ''` | `400` |
| `updated_by` | `BIGINT UNSIGNED` | `NULL` | Actor user ID within same tenant |
| `updated_at` | `DATETIME` | `NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` | DB-maintained audit timestamp |

**Foreign Key Constraints:**
- `fk_tenant_public_policies_tenant`: `FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT`
- `fk_tenant_public_policies_updater`: `FOREIGN KEY (tenant_id, updated_by) REFERENCES tenant_users(tenant_id, user_id) ON DELETE RESTRICT` (composite tenant-membership reference, enforced by `REQUIRED_TENANT_FOREIGN_KEYS` in `petcare/database/readiness.py`).

---

## 3. URL, Input, RBAC, and Audit Guarantees
- **RBAC & CSRF:** Both `GET /store/settings` and `POST /store/settings/public-policies` require `@login_required` + `@admin_required` (`Staff` receives HTTP `403`) and valid CSRF tokens.
- **URL Validation (`_validated_http_url` in `petcare/services/tenant_settings_service.py`):**
  - Wraps `urlsplit` and `.port` parsing to catch `ValueError` / `UnicodeError` cleanly and return `ValidationError` (HTTP `200` with field error, never HTTP `500`).
  - Allows only `http://` or `https://` schemes with a non-empty authority, valid ports (`1–65535` when specified), no whitespace, no embedded credentials (`username`, `password`, or `@` in `netloc`), and no backslashes (`\`) in `netloc`.
  - **Host compatibility & rejection policy (`_is_valid_url_hostname`):**
    - Accepts canonical dotted-quad IPv4 literals (`192.0.2.10`) via strict `ipaddress.IPv4Address` parsing.
    - Accepts bracketed IPv6 literals (`[2001:db8::1]`) via strict `ipaddress.IPv6Address` parsing, explicitly rejecting IPv6 zone/scope identifiers (e.g., `[fe80::1%eth0]`, `[fe80::1%25eth0]`) as non-routable/unsuitable for public storefront links.
    - Accepts valid DNS and IDN hostnames including an optional single trailing DNS root dot (e.g., `https://example.com.`, `https://example.com./terms`, `https://cửahàng.vn./chinh-sach`), validated via IDNA with `1–63` char labels, max `253` chars (without the trailing dot), and a non-numeric / non-hex rightmost label.
    - Explicitly rejects malformed/non-canonical IPv4-like and numeric hosts (e.g., `999.999.999.999`, `256.0.0.1`, `1.2.3.4.5`, `127.1`, `0177.0.0.1`, `0x7f.0.0.1`, `192.0.2.10.`, `example.123`) as well as leading/consecutive/double-trailing dots (`.example.com`, `bad..example.com`, `example.com..`, `.`).
  - `_is_safe_http_href()` re-validates on read so unsafe stored values never become clickable links.
- **Audit Log:** Emits `tenant.public_policies_updated` with `{"changed_fields": [...]}` (field names only, no raw policy values).

---

## 4. Production Upgrade & Forward-Compatible Rollback Sequence
1. Back up database (`scripts/petcare_backup.py create`) and rehearse migration in staging first.
2. Run idempotent initializer `python -m petcare.database.initialize`; confirm `storefront_public_policies_v1` in `schema_migrations` and HTTP `200` on `/readyz`.
3. **Production Rollback Policy:** If rolling back application code to `v2.0.0`, **retain `tenant_public_policies` and all stored policy rows** (`v2.0.0` schema readiness passes cleanly with additive tables present); use forward-fix migrations instead of `DROP TABLE` once owners have saved policy data.

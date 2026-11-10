"""Read-only MySQL runtime schema contract used by health and demo preflight."""


REQUIRED_COLUMNS = {
    "schema_migrations": {"version", "applied_at"},
    "tenants": {
        "id", "name", "slug", "status", "default_currency", "timezone",
        "created_at", "updated_at",
    },
    "tenant_users": {
        "tenant_id", "user_id", "role", "active", "email_activation_pending", "created_at",
    },
    "tenant_invitations": {
        "id", "tenant_id", "email", "email_outbox_id", "token_hash", "role", "created_by", "accepted_by",
        "created_at", "expires_at", "accepted_at", "revoked_at",
    },
    "tenant_owner_transfers": {
        "id", "tenant_id", "requested_by", "target_user_id", "email_outbox_id",
        "created_at", "expires_at", "accepted_at", "cancelled_at",
    },
    "tenant_export_jobs": {
        "id", "tenant_id", "requested_by", "artifact_key", "passphrase_ciphertext", "status",
        "attempt_count", "next_attempt_at", "locked_until", "last_error_code", "result_json",
        "artifact_size", "created_at", "started_at", "completed_at", "expires_at",
    },
    "users": {
        "id", "username", "email", "email_verified_at", "password_hash", "full_name", "preferred_locale", "role", "active",
        "session_version", "created_at",
    },
    "account_tokens": {
        "id", "user_id", "purpose", "token_hash", "created_at", "expires_at", "consumed_at",
    },
    "email_outbox": {
        "id", "payload_ciphertext", "status", "attempt_count", "next_attempt_at", "expires_at",
        "locked_until", "last_error_code", "created_at", "sent_at",
    },
    "login_throttle": {
        "key_hash", "failed_attempts", "window_started_at", "blocked_until", "updated_at",
    },
    "request_throttle": {
        "key_hash", "scope", "window_started_at", "request_count", "updated_at",
    },
    "worker_heartbeats": {
        "worker_name", "instance_id", "started_at", "last_seen_at",
        "last_success_at", "last_error_code",
    },
    "audit_events": {
        "id", "tenant_id", "actor_user_id", "event_type", "entity_type", "entity_id",
        "summary", "details", "created_at",
    },
    "customers": {
        "id", "tenant_id", "full_name", "phone", "address", "active", "created_at", "updated_at",
    },
    "products": {
        "id", "tenant_id", "code", "name", "category", "description", "unit_price",
        "stock_qty", "reorder_level", "photo_filename", "active", "created_at", "updated_at",
    },
    "pets": {
        "id", "tenant_id", "code", "name", "species", "breed", "sex", "birth_date",
        "weight_kg", "coat_color", "eye_color", "appearance_tags", "photo_filename",
        "photo_descriptor", "sale_price", "sale_status", "buyer_id", "sold_at",
        "created_at", "updated_at",
    },
    "pet_photo_lsh": {
        "tenant_id", "pet_id", "hash_version", "band", "bucket_value",
    },
    "invoices": {
        "id", "tenant_id", "customer_id", "created_by", "created_at", "status", "currency_code",
        "paid_at", "note",
    },
    "invoice_items": {
        "id", "tenant_id", "invoice_id", "item_type", "product_id", "pet_id",
        "item_code_snapshot", "name_snapshot", "unit_price", "quantity", "line_total",
    },
    "invoice_refunds": {
        "id", "tenant_id", "invoice_id", "created_by", "request_key", "created_at",
        "method", "note", "currency_code", "refund_total",
    },
    "invoice_refund_items": {
        "id", "tenant_id", "invoice_id", "refund_id", "invoice_item_id",
        "item_type_snapshot", "item_code_snapshot", "item_name_snapshot", "quantity",
        "unit_price", "refund_amount", "disposition",
    },
    "stock_movements": {
        "id", "tenant_id", "product_id", "quantity_delta", "reason", "created_by",
        "invoice_id", "purchase_order_id", "purchase_order_item_id", "refund_id",
        "refund_item_id", "created_at",
    },
    "suppliers": {
        "id", "tenant_id", "name", "contact_name", "phone", "email", "address",
        "active", "created_at", "updated_at",
    },
    "purchase_orders": {
        "id", "tenant_id", "supplier_id", "supplier_name_snapshot", "created_by",
        "created_at", "status", "currency_code", "total_amount", "note",
    },
    "purchase_order_items": {
        "id", "tenant_id", "purchase_order_id", "product_id", "product_code_snapshot",
        "product_name_snapshot", "unit_cost", "quantity_ordered", "quantity_received", "line_total",
    },
    "purchase_order_receipt_requests": {
        "id", "tenant_id", "purchase_order_id", "request_key", "payload_hash", "created_at",
    },
}


REQUIRED_TENANT_FOREIGN_KEYS = {
    ("audit_events", "fk_audit_events_tenant"),
    ("audit_events", "fk_audit_events_tenant_actor"),
    ("tenant_owner_transfers", "fk_tenant_owner_transfers_tenant"),
    ("tenant_owner_transfers", "fk_tenant_owner_transfers_requester"),
    ("tenant_owner_transfers", "fk_tenant_owner_transfers_target"),
    ("customers", "fk_customers_tenant"),
    ("products", "fk_products_tenant"),
    ("pets", "fk_pets_tenant"),
    ("pets", "fk_pets_tenant_buyer"),
    ("pet_photo_lsh", "fk_pet_photo_lsh_tenant_pet"),
    ("invoices", "fk_invoices_tenant"),
    ("invoices", "fk_invoices_tenant_customer"),
    ("invoices", "fk_invoices_tenant_user"),
    ("invoice_items", "fk_invoice_items_tenant"),
    ("invoice_items", "fk_items_tenant_invoice"),
    ("invoice_items", "fk_items_tenant_product"),
    ("invoice_items", "fk_items_tenant_pet"),
    ("invoice_refunds", "fk_invoice_refunds_tenant"),
    ("invoice_refunds", "fk_invoice_refunds_invoice"),
    ("invoice_refunds", "fk_invoice_refunds_creator"),
    ("invoice_refund_items", "fk_invoice_refund_items_tenant"),
    ("invoice_refund_items", "fk_invoice_refund_items_refund"),
    ("invoice_refund_items", "fk_invoice_refund_items_invoice"),
    ("invoice_refund_items", "fk_invoice_refund_items_invoice_line"),
    ("stock_movements", "fk_stock_tenant"),
    ("stock_movements", "fk_stock_tenant_product"),
    ("stock_movements", "fk_stock_tenant_user"),
    ("stock_movements", "fk_stock_tenant_invoice"),
    ("stock_movements", "fk_stock_tenant_purchase_order"),
    ("stock_movements", "fk_stock_tenant_purchase_order_item"),
    ("suppliers", "fk_suppliers_tenant"),
    ("purchase_orders", "fk_purchase_orders_tenant"),
    ("purchase_orders", "fk_purchase_orders_supplier"),
    ("purchase_orders", "fk_purchase_orders_creator"),
    ("purchase_order_items", "fk_purchase_order_items_tenant"),
    ("purchase_order_items", "fk_purchase_order_items_order"),
    ("purchase_order_items", "fk_purchase_order_items_product"),
    ("purchase_order_receipt_requests", "fk_purchase_receipt_requests_tenant"),
    ("purchase_order_receipt_requests", "fk_purchase_receipt_requests_order"),
}


REQUIRED_GLOBAL_FOREIGN_KEYS = {
    ("account_tokens", "fk_account_tokens_user"),
    ("tenant_invitations", "fk_tenant_invitations_email_outbox"),
    ("tenant_owner_transfers", "fk_tenant_owner_transfers_email"),
    ("tenant_export_jobs", "fk_tenant_export_jobs_requester"),
    ("tenant_export_jobs", "fk_tenant_export_jobs_tenant"),
}


def schema_contract_is_ready(cursor):
    """Check runtime columns and database-enforced tenant foreign keys."""
    table_names = tuple(REQUIRED_COLUMNS)
    table_marks = ",".join(["%s"] * len(table_names))
    cursor.execute(
        # B608: only placeholder count is assembled; identifiers come from the
        # module-level REQUIRED_COLUMNS mapping and values stay bound below.
        "SELECT table_name, column_name FROM information_schema.columns "  # nosec B608
        f"WHERE table_schema = DATABASE() AND table_name IN ({table_marks})",
        table_names,
    )
    existing_columns = set(cursor.fetchall())
    required_columns = {
        (table_name, column_name)
        for table_name, columns in REQUIRED_COLUMNS.items()
        for column_name in columns
    }
    if not required_columns.issubset(existing_columns):
        return False

    constraint_names = tuple(
        name for _, name in REQUIRED_TENANT_FOREIGN_KEYS | REQUIRED_GLOBAL_FOREIGN_KEYS
    )
    constraint_marks = ",".join(["%s"] * len(constraint_names))
    cursor.execute(
        # B608: constraint names are the fixed module-level contract; all are
        # bound as values and no request or database value shapes this SQL.
        "SELECT table_name, constraint_name FROM information_schema.table_constraints "  # nosec B608
        "WHERE constraint_schema = DATABASE() AND constraint_type = 'FOREIGN KEY' "
        f"AND constraint_name IN ({constraint_marks})",
        constraint_names,
    )
    existing_foreign_keys = set(cursor.fetchall())
    if not (
        REQUIRED_TENANT_FOREIGN_KEYS.issubset(existing_foreign_keys)
        and REQUIRED_GLOBAL_FOREIGN_KEYS.issubset(existing_foreign_keys)
    ):
        return False

    cursor.execute(
        "SELECT COUNT(DISTINCT version) FROM schema_migrations "
        "WHERE version IN (%s, %s, %s, %s)",
        ("datetime_storage_utc_v1", "purchasing_orders_v1", "invoice_refunds_v1",
         "purchase_receipt_idempotency_v1"),
    )
    marker_count = cursor.fetchone()
    return marker_count is not None and marker_count[0] == 4

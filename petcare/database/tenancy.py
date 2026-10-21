"""Idempotent, additive migration from the original single-store schema."""


BUSINESS_TABLES = (
    "audit_events",
    "customers",
    "products",
    "pets",
    "invoices",
    "invoice_items",
    "stock_movements",
)


def _column_exists(cursor, table, column):
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
        (table, column),
    )
    return cursor.fetchone()[0] > 0


def _index_exists(cursor, table, index):
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.statistics "
        "WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s",
        (table, index),
    )
    return cursor.fetchone()[0] > 0


def _constraint_exists(cursor, table, constraint):
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.table_constraints "
        "WHERE constraint_schema = DATABASE() AND table_name = %s AND constraint_name = %s",
        (table, constraint),
    )
    return cursor.fetchone()[0] > 0


def _add_index(cursor, table, name, columns, unique=False):
    if not _index_exists(cursor, table, name):
        kind = "UNIQUE KEY" if unique else "INDEX"
        cursor.execute(f"ALTER TABLE `{table}` ADD {kind} `{name}` ({columns})")


def _add_foreign_key(cursor, table, name, local_columns, parent_table, parent_columns):
    if not _constraint_exists(cursor, table, name):
        cursor.execute(
            f"ALTER TABLE `{table}` ADD CONSTRAINT `{name}` "
            f"FOREIGN KEY ({local_columns}) REFERENCES `{parent_table}` ({parent_columns}) "
            "ON DELETE RESTRICT"
        )


def migrate_tenancy(cursor):
    """Backfill one legacy store, then add database-level tenant boundaries.

    MySQL DDL auto-commits. The steps are idempotent so an interrupted migration
    can be safely rerun after inspecting the database's current schema state.
    """
    cursor.execute(
        "INSERT INTO tenants (name, slug, status, default_currency, timezone) "
        "VALUES ('PetCare Shop', 'main', 'active', 'VND', 'Asia/Ho_Chi_Minh') "
        "ON DUPLICATE KEY UPDATE slug = VALUES(slug)"
    )
    cursor.execute("SELECT id FROM tenants WHERE slug = 'main'")
    default_tenant_id = cursor.fetchone()[0]

    for table in BUSINESS_TABLES:
        if not _column_exists(cursor, table, "tenant_id"):
            cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN tenant_id BIGINT UNSIGNED NULL")
        cursor.execute(
            f"UPDATE `{table}` SET tenant_id = %s WHERE tenant_id IS NULL",
            (default_tenant_id,),
        )
        cursor.execute(f"ALTER TABLE `{table}` MODIFY COLUMN tenant_id BIGINT UNSIGNED NOT NULL")

    # A previous unconditional backfill could grant `main` access to a user
    # created later for another store. Repair that case when the other store is
    # still waiting for the new owner's email verification.
    cursor.execute(
        "UPDATE tenant_users main_membership "
        "JOIN tenant_users pending_membership "
        "ON pending_membership.user_id = main_membership.user_id "
        "AND pending_membership.tenant_id <> main_membership.tenant_id "
        "SET main_membership.active = 0 "
        "WHERE main_membership.tenant_id = %s AND main_membership.active = 1 "
        "AND pending_membership.active = 0 "
        "AND pending_membership.email_activation_pending = 1",
        (default_tenant_id,),
    )
    cursor.execute(
        "INSERT IGNORE INTO tenant_users (tenant_id, user_id, role, active) "
        "SELECT %s, u.id, IF(u.role = 'admin', 'owner', 'staff'), u.active FROM users u "
        "WHERE NOT EXISTS (SELECT 1 FROM tenant_users existing WHERE existing.user_id = u.id)",
        (default_tenant_id,),
    )

    for table in BUSINESS_TABLES:
        _add_index(cursor, table, f"uq_{table}_tenant_id", "tenant_id, id", unique=True)

    # Legacy deployments had globally unique pet/product codes. Scope these to
    # a store so separate stores can use their own catalog numbering.
    for table in ("products", "pets"):
        cursor.execute(
            "SELECT index_name, MIN(non_unique) non_unique, COUNT(*) column_count, "
            "GROUP_CONCAT(column_name ORDER BY seq_in_index) columns_in_index "
            "FROM information_schema.statistics WHERE table_schema = DATABASE() "
            "AND table_name = %s GROUP BY index_name",
            (table,),
        )
        for row in cursor.fetchall():
            if row[1] == 0 and row[2] == 1 and row[3] == "code":
                cursor.execute(f"ALTER TABLE `{table}` DROP INDEX `{row[0]}`")
        _add_index(cursor, table, f"uq_{table}_tenant_code", "tenant_id, code", unique=True)

    indexes = (
        ("tenant_users", "idx_tenant_signup_cleanup", "active, email_activation_pending, created_at, tenant_id, user_id", False),
        ("customers", "idx_customers_tenant_name", "tenant_id, full_name, id", False),
        ("products", "idx_products_tenant_name", "tenant_id, name, id", False),
        ("pets", "idx_pets_tenant_status_species", "tenant_id, sale_status, species", False),
        ("invoices", "idx_invoices_tenant_created", "tenant_id, created_at, id", False),
    )
    for table, name, columns, unique in indexes:
        _add_index(cursor, table, name, columns, unique)

    foreign_keys = (
        ("audit_events", "fk_audit_events_tenant", "tenant_id", "tenants", "id"),
        ("customers", "fk_customers_tenant", "tenant_id", "tenants", "id"),
        ("products", "fk_products_tenant", "tenant_id", "tenants", "id"),
        ("pets", "fk_pets_tenant", "tenant_id", "tenants", "id"),
        ("invoices", "fk_invoices_tenant", "tenant_id", "tenants", "id"),
        ("invoice_items", "fk_invoice_items_tenant", "tenant_id", "tenants", "id"),
        ("stock_movements", "fk_stock_tenant", "tenant_id", "tenants", "id"),
        ("audit_events", "fk_audit_events_tenant_actor", "tenant_id, actor_user_id", "tenant_users", "tenant_id, user_id"),
        ("pets", "fk_pets_tenant_buyer", "tenant_id, buyer_id", "customers", "tenant_id, id"),
        ("invoices", "fk_invoices_tenant_customer", "tenant_id, customer_id", "customers", "tenant_id, id"),
        ("invoices", "fk_invoices_tenant_user", "tenant_id, created_by", "tenant_users", "tenant_id, user_id"),
        ("invoice_items", "fk_items_tenant_invoice", "tenant_id, invoice_id", "invoices", "tenant_id, id"),
        ("invoice_items", "fk_items_tenant_product", "tenant_id, product_id", "products", "tenant_id, id"),
        ("invoice_items", "fk_items_tenant_pet", "tenant_id, pet_id", "pets", "tenant_id, id"),
        ("stock_movements", "fk_stock_tenant_product", "tenant_id, product_id", "products", "tenant_id, id"),
        ("stock_movements", "fk_stock_tenant_user", "tenant_id, created_by", "tenant_users", "tenant_id, user_id"),
        ("stock_movements", "fk_stock_tenant_invoice", "tenant_id, invoice_id", "invoices", "tenant_id, id"),
    )
    for table, name, local, parent, remote in foreign_keys:
        _add_foreign_key(cursor, table, name, local, parent, remote)

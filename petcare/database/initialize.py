"""Create the current retail schema without dropping existing tables."""

from pathlib import Path

from petcare.database.connection import migration_transaction
from petcare.database.tenancy import migrate_tenancy


SCHEMA_PATH = Path(__file__).with_name("schema.sql")
UTC_DATETIME_MIGRATION = "datetime_storage_utc_v1"


def migrate_datetime_storage_to_utc(cursor):
    """Convert legacy +07:00 wall-clock DATETIME values to UTC exactly once.

    The old application pinned every MySQL session to +07:00. A marker and all
    row updates commit in the same DML transaction, making an interrupted run
    safe to retry even though surrounding MySQL DDL auto-commits.
    """
    cursor.execute(
        "SELECT 1 FROM schema_migrations WHERE version = %s",
        (UTC_DATETIME_MIGRATION,),
    )
    if cursor.fetchone():
        return False

    cursor.execute(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND data_type = 'datetime' "
        "AND table_name <> 'schema_migrations' "
        "ORDER BY table_name, ordinal_position"
    )
    for table_name, column_name in cursor.fetchall():
        # Names originate in information_schema for the selected database.
        cursor.execute(
            f"UPDATE `{table_name}` SET `{column_name}` = "
            f"DATE_SUB(`{column_name}`, INTERVAL 7 HOUR) "
            f"WHERE `{column_name}` IS NOT NULL"
        )
    cursor.execute(
        "INSERT INTO schema_migrations (version) VALUES (%s)",
        (UTC_DATETIME_MIGRATION,),
    )
    return True


def initialize_database():
    statements = [
        statement.strip()
        for statement in SCHEMA_PATH.read_text(encoding="utf-8").split(";")
        if statement.strip()
    ]
    with migration_transaction() as connection:
        cursor = connection.cursor()
        try:
            for statement in statements:
                cursor.execute(statement)
            cursor.execute(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'tenant_export_jobs' "
                "AND column_name = 'expires_at'"
            )
            export_expiry = cursor.fetchone()
            if export_expiry and export_expiry[0] == "NO":
                cursor.execute(
                    "ALTER TABLE tenant_export_jobs MODIFY COLUMN expires_at DATETIME NULL"
                )
            for index_name, columns in (
                ("uq_invoice_item_product", "invoice_id, product_id"),
                ("uq_invoice_item_pet", "invoice_id, pet_id"),
            ):
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.statistics "
                    "WHERE table_schema = DATABASE() AND table_name = 'invoice_items' "
                    "AND index_name = %s",
                    (index_name,),
                )
                if cursor.fetchone()[0] == 0:
                    cursor.execute(
                        f"ALTER TABLE invoice_items ADD UNIQUE KEY {index_name} ({columns})"
                    )
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'tenant_users'"
            )
            membership_columns = {row[0] for row in cursor.fetchall()}
            if "email_activation_pending" not in membership_columns:
                cursor.execute(
                    "ALTER TABLE tenant_users ADD COLUMN email_activation_pending "
                    "TINYINT(1) NOT NULL DEFAULT 0 AFTER active"
                )
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = 'tenant_users' "
                "AND index_name = 'idx_tenant_users_email_activation'"
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "ALTER TABLE tenant_users ADD INDEX idx_tenant_users_email_activation "
                    "(user_id, email_activation_pending)"
                )
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.table_constraints "
                "WHERE constraint_schema = DATABASE() AND table_name = 'tenant_users' "
                "AND constraint_name = 'chk_tenant_users_email_activation_pending'"
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "ALTER TABLE tenant_users ADD CONSTRAINT chk_tenant_users_email_activation_pending "
                    "CHECK (email_activation_pending IN (0, 1))"
                )
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'users'"
            )
            user_columns = {row[0] for row in cursor.fetchall()}
            for column_name, definition in (
                ("email", "VARCHAR(254) NULL"),
                ("email_verified_at", "DATETIME NULL"),
                ("session_version", "INT UNSIGNED NOT NULL DEFAULT 0"),
                ("preferred_locale", "VARCHAR(8) CHARACTER SET ascii NULL"),
            ):
                if column_name not in user_columns:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {definition}")
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.table_constraints "
                "WHERE constraint_schema = DATABASE() AND table_name = 'users' "
                "AND constraint_name = 'chk_users_preferred_locale'"
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "ALTER TABLE users ADD CONSTRAINT chk_users_preferred_locale "
                    "CHECK (preferred_locale IS NULL OR preferred_locale IN ('vi', 'en'))"
                )
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = 'users' "
                "AND index_name = 'uq_users_email'"
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE users ADD UNIQUE KEY uq_users_email (email)")
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'email_outbox'"
            )
            outbox_columns = {row[0] for row in cursor.fetchall()}
            if "expires_at" not in outbox_columns:
                cursor.execute("ALTER TABLE email_outbox ADD COLUMN expires_at DATETIME NULL AFTER next_attempt_at")
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'tenant_invitations'"
            )
            invitation_columns = {row[0] for row in cursor.fetchall()}
            if "email" not in invitation_columns:
                cursor.execute("ALTER TABLE tenant_invitations ADD COLUMN email VARCHAR(254) NULL AFTER tenant_id")
            if "email_outbox_id" not in invitation_columns:
                cursor.execute("ALTER TABLE tenant_invitations ADD COLUMN email_outbox_id BIGINT UNSIGNED NULL AFTER email")
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = 'tenant_invitations' "
                "AND index_name = 'uq_tenant_invitations_outbox'"
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE tenant_invitations ADD UNIQUE KEY uq_tenant_invitations_outbox (email_outbox_id)")
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = 'tenant_invitations' "
                "AND index_name = 'idx_tenant_invitations_email'"
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE tenant_invitations ADD INDEX idx_tenant_invitations_email (tenant_id, email, accepted_at, revoked_at)")
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.table_constraints "
                "WHERE constraint_schema = DATABASE() AND table_name = 'tenant_invitations' "
                "AND constraint_name = 'fk_tenant_invitations_email_outbox'"
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "ALTER TABLE tenant_invitations ADD CONSTRAINT fk_tenant_invitations_email_outbox "
                    "FOREIGN KEY (email_outbox_id) REFERENCES email_outbox(id) ON DELETE SET NULL"
                )
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'pets'"
            )
            pet_columns = {row[0] for row in cursor.fetchall()}
            for column_name, definition in (
                ("eye_color", "VARCHAR(60) NOT NULL DEFAULT ''"),
                ("appearance_tags", "VARCHAR(255) NOT NULL DEFAULT ''"),
                ("photo_filename", "VARCHAR(64) NULL"),
                ("photo_descriptor", "JSON NULL"),
            ):
                if column_name not in pet_columns:
                    cursor.execute(f"ALTER TABLE pets ADD COLUMN {column_name} {definition}")
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'products'"
            )
            product_columns = {row[0] for row in cursor.fetchall()}
            for column_name, definition in (
                ("description", "VARCHAR(500) NOT NULL DEFAULT ''"),
                ("reorder_level", "INT UNSIGNED NOT NULL DEFAULT 5"),
                ("photo_filename", "VARCHAR(64) NULL"),
            ):
                if column_name not in product_columns:
                    cursor.execute(f"ALTER TABLE products ADD COLUMN {column_name} {definition}")
            legacy_vnd_prices = "unit_price" not in product_columns
            if legacy_vnd_prices:
                cursor.execute("ALTER TABLE products ADD COLUMN unit_price DECIMAL(20, 4) NOT NULL DEFAULT 0")
                # The previous release stored every catalog price in VND even
                # though tenants.default_currency existed as unused metadata.
                cursor.execute("UPDATE tenants SET default_currency = 'VND'")
                cursor.execute("UPDATE products SET unit_price = unit_price_vnd")
            cursor.execute(
                "ALTER TABLE products MODIFY COLUMN unit_price_vnd "
                "BIGINT UNSIGNED NOT NULL DEFAULT 0"
            )
            cursor.execute(
                "UPDATE products SET unit_price = unit_price_vnd "
                "WHERE unit_price = 0 AND unit_price_vnd > 0"
            )
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = 'products' "
                "AND index_name = 'idx_products_stock_active'"
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "ALTER TABLE products ADD INDEX idx_products_stock_active (active, stock_qty)"
                )
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'pets'"
            )
            pet_columns = {row[0] for row in cursor.fetchall()}
            if "sale_price" not in pet_columns:
                cursor.execute("ALTER TABLE pets ADD COLUMN sale_price DECIMAL(20, 4) NOT NULL DEFAULT 0")
                cursor.execute("UPDATE pets SET sale_price = sale_price_vnd")
            cursor.execute(
                "ALTER TABLE pets MODIFY COLUMN sale_price_vnd "
                "BIGINT UNSIGNED NOT NULL DEFAULT 0"
            )
            cursor.execute(
                "UPDATE pets SET sale_price = sale_price_vnd "
                "WHERE sale_price = 0 AND sale_price_vnd > 0"
            )
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'invoices'"
            )
            invoice_columns = {row[0] for row in cursor.fetchall()}
            if "currency_code" not in invoice_columns:
                cursor.execute(
                    "ALTER TABLE invoices ADD COLUMN currency_code "
                    "CHAR(3) CHARACTER SET ascii NOT NULL DEFAULT 'VND' AFTER status"
                )
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'invoice_items'"
            )
            item_columns = {row[0] for row in cursor.fetchall()}
            if "unit_price" not in item_columns:
                cursor.execute(
                    "ALTER TABLE invoice_items ADD COLUMN unit_price DECIMAL(20, 4) NOT NULL DEFAULT 0"
                )
                cursor.execute("UPDATE invoice_items SET unit_price = unit_price_vnd")
            if "line_total" not in item_columns:
                cursor.execute(
                    "ALTER TABLE invoice_items ADD COLUMN line_total DECIMAL(20, 4) NOT NULL DEFAULT 0"
                )
                cursor.execute("UPDATE invoice_items SET line_total = line_total_vnd")
            cursor.execute(
                "ALTER TABLE invoice_items MODIFY COLUMN unit_price_vnd "
                "BIGINT UNSIGNED NOT NULL DEFAULT 0"
            )
            cursor.execute(
                "ALTER TABLE invoice_items MODIFY COLUMN line_total_vnd "
                "BIGINT UNSIGNED NOT NULL DEFAULT 0"
            )
            cursor.execute(
                "UPDATE invoice_items SET unit_price = unit_price_vnd "
                "WHERE unit_price = 0 AND unit_price_vnd > 0"
            )
            cursor.execute(
                "UPDATE invoice_items SET line_total = line_total_vnd "
                "WHERE line_total = 0 AND line_total_vnd > 0"
            )
            migrate_datetime_storage_to_utc(cursor)
            migrate_tenancy(cursor)
        finally:
            cursor.close()


if __name__ == "__main__":
    initialize_database()
    print("Đã khởi tạo schema MySQL PetCare Shop.")

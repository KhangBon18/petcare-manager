-- PetCare Manager multi-store SaaS schema. MySQL 8.0.16+, InnoDB, utf8mb4.
CREATE TABLE IF NOT EXISTS tenants (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(160) NOT NULL,
    slug VARCHAR(80) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
    status ENUM('active', 'suspended') NOT NULL DEFAULT 'active',
    default_currency CHAR(3) CHARACTER SET ascii NOT NULL DEFAULT 'VND',
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_tenants_slug (slug),
    CONSTRAINT chk_tenants_slug CHECK (slug REGEXP '^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(254) NULL,
    email_verified_at DATETIME NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(160) NOT NULL,
    preferred_locale VARCHAR(8) CHARACTER SET ascii NULL,
    role ENUM('admin', 'staff') NOT NULL DEFAULT 'staff',
    active TINYINT(1) NOT NULL DEFAULT 1,
    session_version INT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_email (email),
    CONSTRAINT chk_users_active CHECK (active IN (0, 1)),
    CONSTRAINT chk_users_preferred_locale CHECK (preferred_locale IS NULL OR preferred_locale IN ('vi', 'en'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS account_tokens (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    purpose ENUM('email_verification', 'password_reset') NOT NULL,
    token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    consumed_at DATETIME NULL,
    UNIQUE KEY uq_account_tokens_hash (token_hash),
    INDEX idx_account_tokens_user_purpose (user_id, purpose, consumed_at, expires_at),
    CONSTRAINT fk_account_tokens_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS email_outbox (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    payload_ciphertext MEDIUMBLOB NOT NULL,
    status ENUM('pending', 'processing', 'sent', 'failed') NOT NULL DEFAULT 'pending',
    attempt_count TINYINT UNSIGNED NOT NULL DEFAULT 0,
    next_attempt_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NULL,
    locked_until DATETIME NULL,
    last_error_code VARCHAR(64) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at DATETIME NULL,
    INDEX idx_email_outbox_delivery (status, next_attempt_at, locked_until, id),
    INDEX idx_email_outbox_retention (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tenant_users (
    tenant_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    role ENUM('owner', 'admin', 'staff') NOT NULL DEFAULT 'staff',
    active TINYINT(1) NOT NULL DEFAULT 1,
    email_activation_pending TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, user_id),
    UNIQUE KEY uq_tenant_users_user_tenant (user_id, tenant_id),
    INDEX idx_tenant_users_user (user_id),
    INDEX idx_tenant_users_email_activation (user_id, email_activation_pending),
    INDEX idx_tenant_signup_cleanup (active, email_activation_pending, created_at, tenant_id, user_id),
    CONSTRAINT fk_tenant_users_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT fk_tenant_users_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT chk_tenant_users_active CHECK (active IN (0, 1)),
    CONSTRAINT chk_tenant_users_email_activation_pending CHECK (email_activation_pending IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tenant_invitations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    email VARCHAR(254) NULL,
    email_outbox_id BIGINT UNSIGNED NULL,
    token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    role ENUM('admin', 'staff') NOT NULL DEFAULT 'staff',
    created_by BIGINT UNSIGNED NOT NULL,
    accepted_by BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    accepted_at DATETIME NULL,
    revoked_at DATETIME NULL,
    UNIQUE KEY uq_tenant_invitations_token (token_hash),
    UNIQUE KEY uq_tenant_invitations_outbox (email_outbox_id),
    INDEX idx_tenant_invitations_open (tenant_id, accepted_at, revoked_at, expires_at),
    INDEX idx_tenant_invitations_email (tenant_id, email, accepted_at, revoked_at),
    CONSTRAINT fk_tenant_invitations_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT fk_tenant_invitations_email_outbox FOREIGN KEY (email_outbox_id) REFERENCES email_outbox(id) ON DELETE SET NULL,
    CONSTRAINT fk_tenant_invitations_creator FOREIGN KEY (tenant_id, created_by) REFERENCES tenant_users(tenant_id, user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_tenant_invitations_acceptor FOREIGN KEY (tenant_id, accepted_by) REFERENCES tenant_users(tenant_id, user_id) ON DELETE RESTRICT,
    CONSTRAINT chk_tenant_invitations_lifecycle CHECK (
        (accepted_at IS NULL OR revoked_at IS NULL)
        AND ((accepted_at IS NULL) = (accepted_by IS NULL))
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tenant_owner_transfers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    requested_by BIGINT UNSIGNED NOT NULL,
    target_user_id BIGINT UNSIGNED NOT NULL,
    email_outbox_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    accepted_at DATETIME NULL,
    cancelled_at DATETIME NULL,
    UNIQUE KEY uq_tenant_owner_transfers_outbox (email_outbox_id),
    INDEX idx_tenant_owner_transfers_open (tenant_id, accepted_at, cancelled_at, expires_at, id),
    INDEX idx_tenant_owner_transfers_target (tenant_id, target_user_id, accepted_at, cancelled_at, expires_at),
    CONSTRAINT fk_tenant_owner_transfers_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT fk_tenant_owner_transfers_requester FOREIGN KEY (tenant_id, requested_by) REFERENCES tenant_users(tenant_id, user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_tenant_owner_transfers_target FOREIGN KEY (tenant_id, target_user_id) REFERENCES tenant_users(tenant_id, user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_tenant_owner_transfers_email FOREIGN KEY (email_outbox_id) REFERENCES email_outbox(id) ON DELETE SET NULL,
    CONSTRAINT chk_tenant_owner_transfers_distinct_users CHECK (requested_by <> target_user_id),
    CONSTRAINT chk_tenant_owner_transfers_lifecycle CHECK (accepted_at IS NULL OR cancelled_at IS NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tenant_export_jobs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    requested_by BIGINT UNSIGNED NOT NULL,
    artifact_key VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    passphrase_ciphertext MEDIUMBLOB NULL,
    status ENUM('pending', 'processing', 'ready', 'failed') NOT NULL DEFAULT 'pending',
    attempt_count TINYINT UNSIGNED NOT NULL DEFAULT 0,
    next_attempt_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_until DATETIME NULL,
    last_error_code VARCHAR(64) NULL,
    result_json JSON NULL,
    artifact_size BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME NULL,
    completed_at DATETIME NULL,
    expires_at DATETIME NULL,
    UNIQUE KEY uq_tenant_export_jobs_artifact (artifact_key),
    INDEX idx_tenant_export_jobs_delivery (status, next_attempt_at, locked_until, id),
    INDEX idx_tenant_export_jobs_expiry (status, expires_at, id),
    INDEX idx_tenant_export_jobs_requester (tenant_id, requested_by, created_at, id),
    CONSTRAINT fk_tenant_export_jobs_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT fk_tenant_export_jobs_requester FOREIGN KEY (tenant_id, requested_by) REFERENCES tenant_users(tenant_id, user_id) ON DELETE RESTRICT,
    CONSTRAINT chk_tenant_export_jobs_passphrase CHECK (
        (status IN ('pending', 'processing') AND passphrase_ciphertext IS NOT NULL)
        OR (status IN ('ready', 'failed') AND passphrase_ciphertext IS NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS login_throttle (
    key_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,
    failed_attempts SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    window_started_at DATETIME NOT NULL,
    blocked_until DATETIME NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_login_throttle_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS request_throttle (
    key_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    scope VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    window_started_at DATETIME NOT NULL,
    request_count INT UNSIGNED NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (key_hash, scope),
    INDEX idx_request_throttle_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS worker_heartbeats (
    worker_name VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    instance_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_success_at DATETIME NULL,
    last_error_code VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
    PRIMARY KEY (worker_name, instance_id),
    INDEX idx_worker_heartbeats_freshness (worker_name, last_seen_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    actor_user_id BIGINT UNSIGNED NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    entity_type VARCHAR(32) NOT NULL,
    entity_id BIGINT UNSIGNED NULL,
    summary VARCHAR(255) NOT NULL,
    details JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_events_created (created_at, id),
    INDEX idx_audit_events_actor (actor_user_id, created_at),
    INDEX idx_audit_events_entity (entity_type, entity_id, created_at),
    UNIQUE KEY uq_audit_events_tenant_id (tenant_id, id),
    CONSTRAINT fk_audit_events_actor FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_audit_events_tenant_actor FOREIGN KEY (tenant_id, actor_user_id) REFERENCES tenant_users(tenant_id, user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_audit_events_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS customers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    full_name VARCHAR(160) NOT NULL,
    phone VARCHAR(32) NOT NULL,
    address VARCHAR(255) NOT NULL DEFAULT '',
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_customers_name (full_name),
    INDEX idx_customers_phone (phone),
    UNIQUE KEY uq_customers_tenant_id (tenant_id, id),
    INDEX idx_customers_tenant_name (tenant_id, full_name, id),
    CONSTRAINT fk_customers_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT chk_customers_active CHECK (active IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS products (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    code VARCHAR(48) NOT NULL,
    name VARCHAR(160) NOT NULL,
    category VARCHAR(100) NOT NULL,
    description VARCHAR(500) NOT NULL DEFAULT '',
    unit_price DECIMAL(20, 4) NOT NULL DEFAULT 0,
    unit_price_vnd BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Deprecated VND compatibility column, use unit_price.',
    stock_qty INT NOT NULL DEFAULT 0,
    reorder_level INT UNSIGNED NOT NULL DEFAULT 5,
    photo_filename VARCHAR(64) NULL,
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_products_name (name),
    INDEX idx_products_category (category),
    INDEX idx_products_stock_active (active, stock_qty),
    UNIQUE KEY uq_products_tenant_code (tenant_id, code),
    UNIQUE KEY uq_products_tenant_id (tenant_id, id),
    INDEX idx_products_tenant_name (tenant_id, name, id),
    CONSTRAINT fk_products_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT chk_products_price CHECK (unit_price >= 0),
    CONSTRAINT chk_products_stock CHECK (stock_qty >= 0),
    CONSTRAINT chk_products_active CHECK (active IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pets (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    code VARCHAR(48) NOT NULL,
    name VARCHAR(120) NOT NULL,
    species VARCHAR(80) NOT NULL,
    breed VARCHAR(100) NOT NULL DEFAULT '',
    sex ENUM('male', 'female', 'unknown') NOT NULL DEFAULT 'unknown',
    birth_date DATE NULL,
    weight_kg DECIMAL(6, 2) NULL,
    coat_color VARCHAR(80) NOT NULL DEFAULT '',
    eye_color VARCHAR(60) NOT NULL DEFAULT '',
    appearance_tags VARCHAR(255) NOT NULL DEFAULT '',
    photo_filename VARCHAR(64) NULL,
    photo_descriptor JSON NULL,
    sale_price DECIMAL(20, 4) NOT NULL DEFAULT 0,
    sale_price_vnd BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Deprecated VND compatibility column, use sale_price.',
    sale_status ENUM('available', 'sold', 'inactive') NOT NULL DEFAULT 'available',
    buyer_id BIGINT UNSIGNED NULL,
    sold_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_pets_status_species (sale_status, species),
    INDEX idx_pets_name (name),
    UNIQUE KEY uq_pets_tenant_code (tenant_id, code),
    UNIQUE KEY uq_pets_tenant_id (tenant_id, id),
    INDEX idx_pets_tenant_status_species (tenant_id, sale_status, species),
    CONSTRAINT fk_pets_buyer FOREIGN KEY (buyer_id) REFERENCES customers(id) ON DELETE RESTRICT,
    CONSTRAINT fk_pets_tenant_buyer FOREIGN KEY (tenant_id, buyer_id) REFERENCES customers(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_pets_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT chk_pets_price CHECK (sale_price >= 0),
    CONSTRAINT chk_pets_weight CHECK (weight_kg IS NULL OR weight_kg > 0),
    CONSTRAINT chk_pets_buyer_status CHECK (
        (sale_status = 'sold' AND buyer_id IS NOT NULL AND sold_at IS NOT NULL)
        OR (sale_status <> 'sold' AND buyer_id IS NULL AND sold_at IS NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Derived locality-sensitive hash buckets keep image search bounded as a store grows.
-- Full descriptors remain on pets.photo_descriptor and are used for final ranking.
CREATE TABLE IF NOT EXISTS pet_photo_lsh (
    tenant_id BIGINT UNSIGNED NOT NULL,
    pet_id BIGINT UNSIGNED NOT NULL,
    hash_version TINYINT UNSIGNED NOT NULL,
    band TINYINT UNSIGNED NOT NULL,
    bucket_value TINYINT UNSIGNED NOT NULL,
    PRIMARY KEY (tenant_id, pet_id, hash_version, band),
    INDEX idx_pet_photo_lsh_bucket (tenant_id, hash_version, band, bucket_value, pet_id),
    CONSTRAINT fk_pet_photo_lsh_tenant_pet
        FOREIGN KEY (tenant_id, pet_id) REFERENCES pets(tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT chk_pet_photo_lsh_band CHECK (band < 8),
    CONSTRAINT chk_pet_photo_lsh_bucket CHECK (bucket_value < 256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS invoices (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    customer_id BIGINT UNSIGNED NOT NULL,
    created_by BIGINT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('unpaid', 'paid', 'cancelled') NOT NULL DEFAULT 'unpaid',
    currency_code CHAR(3) CHARACTER SET ascii NOT NULL DEFAULT 'VND',
    paid_at DATETIME NULL,
    note VARCHAR(500) NOT NULL DEFAULT '',
    INDEX idx_invoices_customer (customer_id, created_at),
    INDEX idx_invoices_status_paid (status, paid_at),
    UNIQUE KEY uq_invoices_tenant_id (tenant_id, id),
    INDEX idx_invoices_tenant_created (tenant_id, created_at, id),
    CONSTRAINT fk_invoices_customer FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
    CONSTRAINT fk_invoices_user FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_invoices_tenant_customer FOREIGN KEY (tenant_id, customer_id) REFERENCES customers(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_invoices_tenant_user FOREIGN KEY (tenant_id, created_by) REFERENCES tenant_users(tenant_id, user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_invoices_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT chk_invoice_paid_at CHECK (
        (status = 'paid' AND paid_at IS NOT NULL)
        OR (status <> 'paid' AND paid_at IS NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS invoice_items (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    invoice_id BIGINT UNSIGNED NOT NULL,
    item_type ENUM('product', 'pet') NOT NULL,
    product_id BIGINT UNSIGNED NULL,
    pet_id BIGINT UNSIGNED NULL,
    item_code_snapshot VARCHAR(48) NOT NULL,
    name_snapshot VARCHAR(160) NOT NULL,
    unit_price DECIMAL(20, 4) NOT NULL DEFAULT 0,
    unit_price_vnd BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Deprecated VND compatibility column, use unit_price.',
    quantity INT UNSIGNED NOT NULL,
    line_total DECIMAL(20, 4) NOT NULL DEFAULT 0,
    line_total_vnd BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Deprecated VND compatibility column, use line_total.',
    INDEX idx_invoice_items_invoice (invoice_id),
    UNIQUE KEY uq_invoice_item_product (invoice_id, product_id),
    UNIQUE KEY uq_invoice_item_pet (invoice_id, pet_id),
    UNIQUE KEY uq_invoice_items_tenant_id (tenant_id, id),
    CONSTRAINT fk_items_tenant_invoice FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoices(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_items_invoice FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE RESTRICT,
    CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
    CONSTRAINT fk_items_pet FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE RESTRICT,
    CONSTRAINT fk_items_tenant_product FOREIGN KEY (tenant_id, product_id) REFERENCES products(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_items_tenant_pet FOREIGN KEY (tenant_id, pet_id) REFERENCES pets(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_invoice_items_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT chk_invoice_item_target CHECK (
        (item_type = 'product' AND product_id IS NOT NULL AND pet_id IS NULL AND quantity > 0)
        OR (item_type = 'pet' AND product_id IS NULL AND pet_id IS NOT NULL AND quantity = 1)
    ),
    CONSTRAINT chk_invoice_item_total CHECK (line_total = unit_price * quantity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stock_movements (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    product_id BIGINT UNSIGNED NOT NULL,
    quantity_delta INT NOT NULL,
    reason VARCHAR(255) NOT NULL,
    created_by BIGINT UNSIGNED NOT NULL,
    invoice_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stock_product_created (product_id, created_at),
    INDEX idx_stock_invoice (invoice_id),
    UNIQUE KEY uq_stock_movements_tenant_id (tenant_id, id),
    CONSTRAINT fk_stock_tenant_product FOREIGN KEY (tenant_id, product_id) REFERENCES products(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_user FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_invoice FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_tenant_user FOREIGN KEY (tenant_id, created_by) REFERENCES tenant_users(tenant_id, user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_tenant_invoice FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoices(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT chk_stock_delta CHECK (quantity_delta <> 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

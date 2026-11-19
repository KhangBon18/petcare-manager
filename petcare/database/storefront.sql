-- Additive Customer Storefront tables. Executed after core schema and tenancy
-- indexes so all composite tenant-scoped foreign keys resolve deterministically.
CREATE TABLE IF NOT EXISTS customer_accounts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    email VARCHAR(254) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(160) NOT NULL,
    phone VARCHAR(32) NOT NULL DEFAULT '',
    default_address VARCHAR(255) NOT NULL DEFAULT '',
    active TINYINT(1) NOT NULL DEFAULT 1,
    session_version INT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_customer_accounts_tenant_id (tenant_id, id),
    UNIQUE KEY uq_customer_accounts_tenant_email (tenant_id, email),
    INDEX idx_customer_accounts_tenant_name (tenant_id, full_name, id),
    CONSTRAINT fk_customer_accounts_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT chk_customer_accounts_active CHECK (active IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS customer_orders (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    order_code VARCHAR(32) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
    request_key CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    customer_account_id BIGINT UNSIGNED NULL,
    customer_id BIGINT UNSIGNED NULL,
    invoice_id BIGINT UNSIGNED NULL,
    processed_by BIGINT UNSIGNED NULL,
    customer_name VARCHAR(160) NOT NULL,
    customer_phone VARCHAR(32) NOT NULL,
    customer_email VARCHAR(254) NOT NULL DEFAULT '',
    delivery_address VARCHAR(255) NOT NULL DEFAULT '',
    fulfillment_method ENUM('pickup', 'cod_delivery') NOT NULL DEFAULT 'pickup',
    payment_method ENUM('pay_at_store', 'cod') NOT NULL DEFAULT 'pay_at_store',
    payment_status ENUM('unpaid', 'paid') NOT NULL DEFAULT 'unpaid',
    order_status ENUM('pending', 'confirmed', 'preparing', 'fulfilled', 'ready_completed', 'rejected', 'cancelled') NOT NULL DEFAULT 'pending',
    currency_code CHAR(3) CHARACTER SET ascii NOT NULL DEFAULT 'VND',
    total_amount DECIMAL(20, 4) NOT NULL DEFAULT 0,
    customer_note VARCHAR(500) NOT NULL DEFAULT '',
    staff_note VARCHAR(500) NOT NULL DEFAULT '',
    confirmed_at DATETIME NULL,
    fulfilled_at DATETIME NULL,
    completed_at DATETIME NULL,
    cancelled_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_customer_orders_tenant_id (tenant_id, id),
    UNIQUE KEY uq_customer_orders_tenant_code (tenant_id, order_code),
    UNIQUE KEY uq_customer_orders_tenant_request (tenant_id, request_key),
    INDEX idx_customer_orders_tenant_status_created (tenant_id, order_status, created_at, id),
    INDEX idx_customer_orders_tenant_account (tenant_id, customer_account_id, created_at, id),
    INDEX idx_customer_orders_tenant_phone (tenant_id, customer_phone, id),
    CONSTRAINT fk_customer_orders_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT fk_customer_orders_account
        FOREIGN KEY (tenant_id, customer_account_id) REFERENCES customer_accounts(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_customer_orders_customer
        FOREIGN KEY (tenant_id, customer_id) REFERENCES customers(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_customer_orders_invoice
        FOREIGN KEY (tenant_id, invoice_id) REFERENCES invoices(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_customer_orders_processor
        FOREIGN KEY (tenant_id, processed_by) REFERENCES tenant_users(tenant_id, user_id) ON DELETE RESTRICT,
    CONSTRAINT chk_customer_orders_total CHECK (total_amount >= 0),
    CONSTRAINT chk_customer_orders_currency CHECK (currency_code REGEXP '^[A-Z]{3}$'),
    CONSTRAINT chk_customer_orders_fulfillment_payment CHECK (
        (fulfillment_method = 'pickup' AND payment_method IN ('pay_at_store', 'cod'))
        OR (fulfillment_method = 'cod_delivery' AND payment_method = 'cod')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS customer_order_items (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    order_id BIGINT UNSIGNED NOT NULL,
    item_type ENUM('product', 'pet') NOT NULL,
    product_id BIGINT UNSIGNED NULL,
    pet_id BIGINT UNSIGNED NULL,
    item_code_snapshot VARCHAR(48) NOT NULL,
    name_snapshot VARCHAR(160) NOT NULL,
    unit_price DECIMAL(20, 4) NOT NULL DEFAULT 0,
    quantity INT UNSIGNED NOT NULL,
    line_total DECIMAL(20, 4) NOT NULL DEFAULT 0,
    UNIQUE KEY uq_customer_order_items_tenant_id (tenant_id, id),
    UNIQUE KEY uq_customer_order_item_product (tenant_id, order_id, product_id),
    UNIQUE KEY uq_customer_order_item_pet (tenant_id, order_id, pet_id),
    INDEX idx_customer_order_items_order (tenant_id, order_id, id),
    INDEX idx_customer_order_items_product (tenant_id, product_id, order_id),
    INDEX idx_customer_order_items_pet (tenant_id, pet_id, order_id),
    CONSTRAINT fk_customer_order_items_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT fk_customer_order_items_order
        FOREIGN KEY (tenant_id, order_id) REFERENCES customer_orders(tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_customer_order_items_product
        FOREIGN KEY (tenant_id, product_id) REFERENCES products(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_customer_order_items_pet
        FOREIGN KEY (tenant_id, pet_id) REFERENCES pets(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT chk_customer_order_item_target CHECK (
        (item_type = 'product' AND product_id IS NOT NULL AND pet_id IS NULL AND quantity > 0)
        OR (item_type = 'pet' AND product_id IS NULL AND pet_id IS NOT NULL AND quantity = 1)
    ),
    CONSTRAINT chk_customer_order_item_total CHECK (unit_price >= 0 AND line_total = unit_price * quantity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Guarantees atomic database-level exclusivity for pets held by confirmed/preparing online orders.
CREATE TABLE IF NOT EXISTS customer_order_pet_locks (
    tenant_id BIGINT UNSIGNED NOT NULL,
    pet_id BIGINT UNSIGNED NOT NULL,
    order_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, pet_id),
    UNIQUE KEY uq_customer_order_pet_locks_order_pet (tenant_id, order_id, pet_id),
    CONSTRAINT fk_customer_order_pet_locks_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT fk_customer_order_pet_locks_pet
        FOREIGN KEY (tenant_id, pet_id) REFERENCES pets(tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_customer_order_pet_locks_order
        FOREIGN KEY (tenant_id, order_id) REFERENCES customer_orders(tenant_id, id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


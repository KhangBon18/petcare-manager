-- Additive purchasing tables. Executed after the legacy tenancy migration so
-- the referenced tenant-scoped indexes already exist on upgraded databases.
CREATE TABLE IF NOT EXISTS suppliers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(160) NOT NULL,
    contact_name VARCHAR(160) NOT NULL DEFAULT '',
    phone VARCHAR(32) NOT NULL DEFAULT '',
    email VARCHAR(254) NOT NULL DEFAULT '',
    address VARCHAR(255) NOT NULL DEFAULT '',
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_suppliers_tenant_id (tenant_id, id),
    UNIQUE KEY uq_suppliers_tenant_name (tenant_id, name),
    INDEX idx_suppliers_tenant_active_name (tenant_id, active, name, id),
    CONSTRAINT fk_suppliers_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT chk_suppliers_active CHECK (active IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS purchase_orders (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    supplier_id BIGINT UNSIGNED NOT NULL,
    supplier_name_snapshot VARCHAR(160) NOT NULL,
    created_by BIGINT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('ordered', 'partially_received', 'received', 'cancelled') NOT NULL DEFAULT 'ordered',
    currency_code CHAR(3) CHARACTER SET ascii NOT NULL,
    total_amount DECIMAL(20, 4) NOT NULL DEFAULT 0,
    note VARCHAR(500) NOT NULL DEFAULT '',
    UNIQUE KEY uq_purchase_orders_tenant_id (tenant_id, id),
    INDEX idx_purchase_orders_tenant_created (tenant_id, created_at, id),
    INDEX idx_purchase_orders_tenant_status (tenant_id, status, created_at, id),
    INDEX idx_purchase_orders_supplier (tenant_id, supplier_id, created_at, id),
    CONSTRAINT fk_purchase_orders_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT fk_purchase_orders_supplier FOREIGN KEY (tenant_id, supplier_id) REFERENCES suppliers(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_purchase_orders_creator FOREIGN KEY (tenant_id, created_by) REFERENCES tenant_users(tenant_id, user_id) ON DELETE RESTRICT,
    CONSTRAINT chk_purchase_orders_total CHECK (total_amount >= 0),
    CONSTRAINT chk_purchase_orders_currency CHECK (currency_code REGEXP '^[A-Z]{3}$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tenant_id BIGINT UNSIGNED NOT NULL,
    purchase_order_id BIGINT UNSIGNED NOT NULL,
    product_id BIGINT UNSIGNED NOT NULL,
    product_code_snapshot VARCHAR(48) NOT NULL,
    product_name_snapshot VARCHAR(160) NOT NULL,
    unit_cost DECIMAL(20, 4) NOT NULL,
    quantity_ordered INT UNSIGNED NOT NULL,
    quantity_received INT UNSIGNED NOT NULL DEFAULT 0,
    line_total DECIMAL(20, 4) NOT NULL,
    UNIQUE KEY uq_purchase_order_items_tenant_id (tenant_id, id),
    UNIQUE KEY uq_purchase_order_items_tenant_order_id (tenant_id, purchase_order_id, id),
    UNIQUE KEY uq_purchase_order_items_product (tenant_id, purchase_order_id, product_id),
    INDEX idx_purchase_order_items_product (tenant_id, product_id, purchase_order_id),
    CONSTRAINT fk_purchase_order_items_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT,
    CONSTRAINT fk_purchase_order_items_order FOREIGN KEY (tenant_id, purchase_order_id) REFERENCES purchase_orders(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_purchase_order_items_product FOREIGN KEY (tenant_id, product_id) REFERENCES products(tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT chk_purchase_order_items_quantity CHECK (
        quantity_ordered > 0 AND quantity_received <= quantity_ordered
    ),
    CONSTRAINT chk_purchase_order_items_cost CHECK (unit_cost >= 0 AND line_total = unit_cost * quantity_ordered)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

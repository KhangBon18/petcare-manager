# Admin & Staff Operations Guide (`ADMIN_STAFF_GUIDE.md`)

Guide for internal store personnel using the **PetCare Manager Workspace** (`/login` -> `/dashboard`).

---

## 1. Roles & Access Control

- **Owner (`admin` + ownership flag)**: Full store administration, settings (`/store/settings`), member invitations & ownership transfer (`/users/`, `/users/ownership`), encrypted tenant data export, purchasing, refunds, and activity logs.
- **Admin (`admin`)**: Full catalog, customer, POS, online order fulfillment, purchasing, supplier, refund, reporting, AI workspace, and store user management (cannot deactivate or demote an owner).
- **Staff (`staff`)**: Day-to-day operations — Dashboard KPIs, Customer CRUD & history, Product/Pet lookup, Visual Pet Search, POS billing & payment collection, Online Order processing (`/orders/`), and Read-Only Staff AI Assistant. Restricted from store settings, user administration, purchasing/suppliers, refunds, full financial exports, and audit logs.
- **Multi-Store Switching**: Users assigned to multiple stores can switch active tenant via `POST /switch-store` in the top header. Permissions and queries reload cleanly per tenant from MySQL on every request.

---

## 2. Core Daily Workflows

### 2.1 Dashboard (`/dashboard`)
- Displays net paid revenue (`today`, `7d`, `30d`, `this_month`), active customers, active products, available pets, low-stock alerts, 8-week weighted demand restock priorities, recent paid invoices, and quick shortcuts.

### 2.2 Customers, Pets & Products (`/customers/`, `/pets/`, `/products/`)
- **Customers**: Search by name/phone, view paginated invoice history split by currency, deactivate/reactivate inactive accounts, or launch a pre-filled POS invoice.
- **Pets**: Manage per-individual records (`code`, `species`, `breed`, `sex`, `coat_color`, `eye_color`, `appearance_tags`, `sale_price`, `sale_status`) and upload up to **5 reference photos** (`JPEG/PNG/WebP <= 5 MB`, EXIF stripped, stored privately via authenticated `pets.photo` route). Sold pets cannot be resold or edited into double-sales.
- **Products**: Maintain SKUs, prices (`DECIMAL(20,4)`), reorder thresholds, stock adjustments (every change logs `stock_movements` + audit trail), and private product photos.

### 2.3 POS Billing & Refunds (`/invoices/`)
- **Unpaid Invoices Do Not Reserve Stock**: Creating an unpaid draft (`POST /invoices/new`) freezes line item snapshots without deducting inventory.
- **Atomic Payment (`POST /invoices/<id>/pay`)**: Locks the invoice and catalog rows in ascending ID order inside an InnoDB transaction, re-validates available quantity/pet status, writes negative `stock_movements`, marks pets `sold` (`buyer_id`), and commits `paid` idempotently.
- **Refunds (Admin only, `POST /invoices/<id>/refund`)**: Recorded in the separate refund ledger (`invoice_refunds`, `invoice_refund_items`) with per-line restock disposition (`restock` returns stock / makes pet available again vs non-restocking goodwill) and `request_key` idempotency. Original paid invoices remain immutable; reports automatically compute **net revenue**.

### 2.4 Suppliers & Partial Purchasing (`/purchasing/`)
- Manage active/archived suppliers (`/purchasing/suppliers`), create multi-line POs (`<= 100` lines, unit costs snapshotted at creation), receive deliveries across multiple partial batches (`purchase_order_receipt_requests` prevents duplicate submissions), and close remaining undelivered quantities safely without altering previously received inventory.

### 2.5 Online Order Queue & COD Fulfillment (`/orders/`)
- Staff/Admin process pending storefront orders placed via `/shop/checkout`:
  1. `pending`: Initial state submitted by customer. Stock is **not** locked yet.
  2. **`Confirm` (`confirmed`)**: Reserves product quantities and acquires `customer_order_pet_locks` for pets inside a MySQL transaction. Rejected automatically if concurrent POS sales already consumed stock or sold the pet.
  3. **`Prepare` (`preparing`)**: Marks order items being packed.
  4. **`Mark Ready / Delivered` (`ready_completed`)**: Marks order ready at counter or handed off for delivery (**remains `unpaid` until cash/payment is explicitly confirmed**).
  5. **`Confirm Payment` (`confirm_payment`)**: Explicitly validates cash collection, issues a linked `paid` invoice in `invoices`/`invoice_items`, records `stock_movements`, marks pets `sold`, releases locks, and completes fulfillment.
  6. **`Reject` / `Cancel` (`rejected` / `cancelled`)**: Releases reserved product allocations and `customer_order_pet_locks` cleanly without touching paid ledger entries (only valid before payment is collected).

### 2.6 Internal AI Workspace & Visual Search (`/assistant/chat`, `/pets/find-similar`)
- **AI Workspace (`/assistant/chat`)**: Supports Store Mode (full operational/inventory/top-products insights by role) and Shopper Preview QA Mode. Also accessible on any standard internal page via the topbar **Ask Assistant** (`#assistant-launcher`) drawer.
- **Visual Search (`/pets/find-similar`)**: Upload or capture via webcam (on HTTPS or localhost; LAN mobile upload via QR when `LAN_ACCESS_ENABLED=1`) to run local ONNX species verification (`Cat`/`Dog`) + similarity ranking across `pet_reference_photos`. Always treat scores (`.../100`) as visual similarity guidance for human verification, never automated identity proof.
- **Activity Audit (`/activity/`, Admin only)**: Read-only paginated audit trail (`25/page`) recording login/logout events, inventory edits, PO receipts, invoice payments, refunds, and online order state transitions.

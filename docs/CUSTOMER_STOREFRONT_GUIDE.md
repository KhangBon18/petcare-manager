# Customer Storefront Guide (`CUSTOMER_STOREFRONT_GUIDE.md`)

Guide to the public-facing e-commerce experience at `/shop`.

---

## 1. Routes & Storefront Capabilities

| Route | Function | Authentication |
|---|---|---|
| `/shop` | Landing hero, search bar, AI tool strip, featured available pets & top products | Public |
| `/shop/products` & `/shop/products/<id>` | Browse/filter products by keyword/category, check real-time available stock, add to cart | Public |
| `/shop/pets` & `/shop/pets/<id>` | Browse available pets (hides sold or order-locked pets where applicable), inspect photos/specs | Public |
| `/shop/image-search` | Upload a cat/dog photo (JPEG/PNG/WebP `<= 5 MB`) for local ONNX visual similarity matching | Public (IP rate-limited) |
| `/shop/ai-assistant` | Shopping AI concierge for pet recommendations, product comparisons, and pet-care Q&A | Public (IP rate-limited) |
| `/shop/cart` | View cart, adjust quantities (bounded by real available inventory), remove items | Public (session cart) |
| `/shop/checkout` | Place a pending order with **Store Pickup** or **Cash on Delivery (COD)** | Optional login (pre-fills if signed in) |
| `/shop/order-lookup` & `/shop/orders/<code>` | Track order status (`ORDER_CODE` + phone verification) | Public (`POST` lookup) / Owner |
| `/shop/login`, `/shop/register`, `/shop/account` | Customer registration/sign-in, profile contact updates, responsive order history | Customer account |

---

## 2. Stock Availability, Reservations & Conditional Checkout

- **Real-Time Available Quantity**: Displayed product stock equals `products.stock_qty` minus quantities reserved by active `confirmed`/`preparing` online orders. Pets locked inside `customer_order_pet_locks` cannot be reserved twice or sold at POS.
- **Checkout Fulfillment Options (`/shop/checkout`)**:
  - **Store Pickup (`pickup`)**: Hides and disables the delivery address input (`#checkout-address-group`); customer pays at the counter upon arrival (`No delivery fee`).
  - **Cash on Delivery (`cod_delivery`)**: Dynamically shows and requires `#checkout-address`; notes clearly that **no online shipping fee is charged** and staff confirm delivery arrangements directly before dispatch.
- **Payment Semantics (COD / Pay-at-Store Only)**: Placing an order creates a **`pending` / `unpaid`** order. No online payment gateway is integrated. Inventory deduction and `paid` revenue posting happen **only** when staff confirm payment in `/orders/<id>`.

---

## 3. Storefront Images, Account & Responsiveness

- **Verified vs Illustrative Photos**:
  - Stored demo/store photos served via `storefront.public_pet_photo` / `storefront.public_product_photo` are synthetic or uploaded catalog images.
  - Items without stored photos display local fallback vector illustrations (`petcare/static/img/catalog/fallbacks/*.svg`) clearly labeled **"Minh họa" / "Illustrative"**.
- **Responsive Design**: Built cleanly under Option A across desktop (`1440px`), tablet (`834px`), and mobile (`390px`, `320px`), with a fixed 5-tab mobile bottom dock (`<= 720px`) and card-based order history on `/shop/account` so `"Chi tiết"` actions stay 100% visible at `320px`.

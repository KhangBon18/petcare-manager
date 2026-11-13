# PetCare AI — Product Vision & 3C UX Strategy

## 1. Strategic Product Pivot

**Vietnamese Topic**: *"Xây dựng trợ lý AI tư vấn và gợi ý sản phẩm thông minh cho cửa hàng thú cưng bằng Python"*
**English Product Name**: **PetCare AI — Intelligent Pet Shopping & Care Assistant**

Petcare Manager began as a multi-tenant Flask/Jinja2/MySQL retail operations system (catalog, POS invoicing, partial-receipt purchasing, refunds, audit logs, Python-first visual pet search, and 8-week weighted inventory demand forecasting).

Under this product pivot, **PetCare AI becomes the primary user experience**, while the retail management stack serves as the **authoritative, transactional source of truth**:
- Every pet card, product price, normalized unit cost, stock count, and operational metric displayed in chat is grounded strictly in authorized MySQL services.
- Instead of an auxiliary floating FAQ widget, users enter a **dedicated full-page AI workspace** (`GET /assistant/chat`) prominently featured in primary navigation (`Trợ lý AI` / `AI Assistant`) and Dashboard CTAs, while keeping the floating launcher (`#assistant-launcher`) available on non-workspace pages as an optional quick shortcut.
- Because the application does not expose an unauthenticated public storefront, customer-facing shopping journeys are delivered safely through a strictly scoped **Shopper Preview (QA)** mode (`scope="shopper_preview"`) inside authenticated tenant sessions—blocking internal store KPIs, purchase orders, and restock thresholds while allowing realistic end-to-end shopper testing.

---

## 2. 3C Competitive & Pattern Analysis (Copy · Customize · Create)

We analyzed official product patterns across **Shopify Sidekick**, **Chewy (Pet Advice, Connect with a Vet & Personalized Pet Profiles)**, and established **AI commerce shopping assistants** (Amazon Rufus / Shopify Magic). No proprietary code or assets were copied.

| Reference System | Observed Strengths | Relevance to PetCare AI |
|---|---|---|
| **Shopify Sidekick** | Full-workspace co-pilot alongside store navigation; contextual starter prompts; operational summaries grounded in live merchant data; strict human-in-the-loop approval (never mutates store records silently). | Inspires our dual-mode **Store Workspace** (`workspace`) vs **Shopper Preview** (`shopper_preview`), starter prompt groups, and strict read-only safety boundary. |
| **Chewy Pet Advice & Shopping UX** | Species + life-stage + weight-aware product filtering; unit-price transparency (`$/lb`, `$/oz`); clear separation between general pet-care education and licensed veterinary triage. | Inspires our `PreferenceSlots` memory, exact `Decimal` unit-price normalization (`VND/kg`, `VND/100g`, `VND/L`, `VND/tờ`), and mandatory veterinary safety banners. |
| **AI Shopping Assistant UX Patterns** | Multi-turn slot clarification instead of premature noisy dumps; structured product cards with stock badges; side-by-side comparison matrices; clickable follow-up chips. | Inspires our 2-turn guided discovery flow, interactive checkbox Compare Tray (`2–4` SKUs), and collapsible score breakdowns. |

### 3C Synthesis Matrix

1. **COPY (Conceptual UX Patterns Adopted)**
   - Dedicated full-page conversational workspace with categorized starter prompts, active context filter bar, and one-click follow-up chips.
   - Embedded rich catalog cards displaying photo, verified price, live stock badge, and direct profile link.
   - Strict read-only operational posture: the assistant advises and links to forms/POS, never auto-creating invoices, orders, or refunds.

2. **CUSTOMIZE (Adapted to Petcare Manager's Flask/Jinja/MySQL Stack)**
   - **Server-rendered Jinja + progressive Vanilla JS (`assistant_workspace.js`)** adhering to strict Content Security Policy (`script-src 'self'; style-src 'self'`, zero inline styles or scripts) and existing design tokens (`tokens.css`, `app.css`).
   - **Bilingual Vietnamese & English (`vi` / `en`)** NLU, slot chips, unit prices, citations, and safety notices—including Vietnamese diacritic disambiguation (e.g., `"cát vệ sinh"` vs `"cat"`, `"căn hộ"` vs `"hổ phách"`).
   - **Role & Scope Dual Enforcement**: `admin` vs `staff` RBAC combined with `workspace` vs `shopper_preview` scope isolation per `(tenant_id, user_id, scope, conversation_id)`.

3. **CREATE (Original PetCare AI Differentiators)**
   - **Zero-Stereotype Explainable Pet Matching (`0–100` pts)**: Hard constraints (species, `available` status, budget ceiling) run first, followed by transparent point breakdowns where **undocumented attributes (`birth_date=None`, `weight_kg=None`, blank traits) are marked `"unknown"` with `0` bonus points and explicit warnings**—never guessing temperament or apartment suitability from breed names alone.
   - **Exact `Decimal` Package Unit Normalization & Comparison**: Deterministic extraction of `kg`, `g`, `L`, `ml`, `tờ/miếng/viên` to rank and compare products side-by-side on normalized cost (`VND/kg`, `VND/100g`, `VND/L`, `VND/tờ`), with responsive desktop tables and zero-overflow `320px` mobile stacked cards.
   - **Grounded Okapi BM25 Knowledge + Triage Guardrail**: Offline, zero-hallucination retrieval over reviewed reference guidelines (`WSAVA`, `AVMA`, `AAFP/ISFM`, `ASPCA`, `Cornell`) paired with automatic emergency symptom escalation and strict refusal of medical diagnosis or drug dosages.

---

## 3. Core User Journeys

1. **Multi-Turn Apartment Pet Discovery**: User asks *"Tôi muốn nuôi mèo hợp căn hộ"* → Assistant detects missing budget/temperament and asks a focused clarification → User replies *"Hiền, dưới 8 triệu VND"* → Assistant merges session slots, filters `available` cats `<= 8,000,000 VND`, and renders explainable Top-K pet cards with verified traits and unknown-data warnings.
2. **Personalized Product Selection & Comparison**: User asks *"Which food should I consider for my adult cat?"* → Assistant ranks in-stock cat foods with `VND/kg` / `VND/100g` unit prices → User selects 2–4 checkboxes in the Compare Tray (or types *"Compare these three products"*) → Assistant renders a structured side-by-side comparison matrix.
3. **Trusted Care Guidance & Veterinary Safety**: User asks about litter box setup (`N + 1` rule) or 7–10 day food transitions → Assistant answers from BM25-retrieved reviewed articles with clickable citations and a non-veterinarian disclaimer; urgent toxin/respiratory queries trigger immediate emergency clinic escalation.
4. **Authorized Store Operations (`workspace` only)**: Store admins query 8-week weighted demand forecasts (`estimate_weighted_demand`), supplier PO status, and top-selling SKUs; switching to `Shopper Preview (QA)` immediately locks all internal operational tools.

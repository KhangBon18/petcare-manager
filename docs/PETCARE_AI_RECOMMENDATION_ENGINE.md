# PetCare AI — Pet Matching & Product Recommendation Engines

## 1. Two-Stage Explainable Pet Matching (`petcare/ai/recommender_pets.py`)

### 1.1 Stage 1: Hard Constraint Filtering
Every candidate row from `pets` (`WHERE tenant_id = @petcare_tenant_id AND sale_status = 'available'`) must satisfy all explicit hard constraints before receiving any score:
1. **Availability**: `sale_status == "available"` (sold or inactive pets are never recommended).
2. **Species**: Normalized `species` (`"cat"` vs `"dog"`) must match `slots.species`.
3. **Budget Ceiling / Floor**: `sale_price <= slots.budget_max` and `sale_price >= slots.budget_min` using exact `Decimal` arithmetic.
4. **Explicit Sex Filter**: When `slots.sex` is specified (`"male"` or `"female"`), mismatches are excluded.

### 1.2 Stage 2: Explainable 100-Point Scoring & Zero-Stereotype Policy
Each surviving pet $p$ receives a transparent score $S_{\text{pet}}(p) \in [0, 100]$ decomposed into four auditable `ScoreComponent` buckets:

$$
S_{\text{pet}}(p) = S_{\text{budget}}(p) + S_{\text{space}}(p) + S_{\text{temperament}}(p) + S_{\text{completeness}}(p)
$$

| Criterion | Max Points | Scoring Logic & Unknown-Attribute Policy |
|---|---|---|
| `budget_fit` | `30` | `30` pts when comfortably within target ceiling ($\le 85\%$ of `budget_max`), `24` pts near ceiling ($85\%\text{–}100\%$), `22` pts neutral when no budget specified. |
| `space_size_fit` | `25` | Uses **only** verified `weight_kg` and documented `appearance_tags` (`"nhỏ gọn"`, `"lớn"`). For `living_space="apartment"`, verified compact weight ($\le 5.5\text{ kg}$) earns `22` pts (capped below `25` with an explicit note that `apartment_suitable` is not a dedicated DB column). If `weight_kg` and size tags are absent, status is `"unknown"` and **0 bonus points** are awarded. |
| `temperament_care_fit` | `25` | Uses **only** documented `appearance_tags` (`"hiền"`, `"thân thiện"`, `"năng động"`). **Never infers temperament from `breed` alone.** Undocumented temperament receives `0` bonus points (`status="unknown"`) plus an explicit user warning; `"lông dài/dày/xù"` triggers a daily grooming warning. |
| `age_profile_completeness` | `20` | Verified `birth_date` life-stage match (`junior < 12m`, `adult >= 12m`) + documented coat/eye/photo completeness. Missing `birth_date` is labeled `"Undocumented"` / `"Chưa ghi nhận"` with `0` age-match bonus. |

**Deterministic Tie-Breaking**: Candidates sort by `(-score, sale_price, id)` and return Top-$K$ ($K \le 5$).
**Time Complexity**: $O(N_{\text{pets}} \log N_{\text{pets}})$ per tenant, $O(N_{\text{pets}})$ space.

---

## 2. Personalized Product Recommendation Engine (`petcare/ai/recommender_products.py`)

### 2.1 Exact `Decimal` Package Unit Normalization
`parse_package_unit(name, description, unit_price)` extracts verified package quantities (`kg`, `g`, `L`, `ml`, `tờ/miếng`, `viên`, `m`) via bounded regex and computes normalized `Decimal` comparison costs:

- **Mass (`mass_kg`)**:
  - `kg`: $\text{cost}_{\text{kg}} = \frac{\text{unit\_price}}{\text{amount}}$ (`VND/kg`)
  - `g`: displays `VND/100g` ($\frac{\text{unit\_price}}{\text{amount}} \times 100$) and normalizes $\text{cost}_{\text{kg}} = \frac{\text{unit\_price}}{\text{amount} / 1000}$ so `85g` pouches and `1.5kg` bags compare on an identical `VND/kg` basis.
- **Volume (`vol_l`)**:
  - `L`: $\text{cost}_{\text{L}} = \frac{\text{unit\_price}}{\text{amount}}$ (`VND/L`); `ml`: displays `VND/100ml` and normalizes to `VND/L`.
- **Count (`count`)**:
  - `tờ / miếng / viên`: $\text{cost}_{\text{unit}} = \frac{\text{unit\_price}}{\text{amount}}$ (`VND/tờ`, `VND/viên`).

### 2.2 Candidate Filtering, Allergy Safety & Out-of-Stock Fallback
1. **Verified Metadata Extraction (`extract_verified_product_meta`)**: Parses `name`, `category`, and `description` for verified species (`cat`, `dog`, `both`, `unspecified`), life stage (`junior`, `adult`, `all`, `unspecified`), normalized category (`food`, `toy`, `litter`, `care`, `accessory`), and mentioned proteins/ingredients (`chicken`, `salmon`, `beef`, `grain`, `soy`). **Never fabricates nutrient percentages or veterinary certifications.**
2. **Hard Exclusions**:
   - Session-supplied `allergies` (e.g., `"allergic to chicken"` / `"dị ứng gà"`) strictly exclude matching SKUs, accompanied by a non-diagnostic reminder.
   - Pet weight constraints (e.g., `5 kg` cat) exclude accessories explicitly rated only for smaller weights or tiny breeds (`small_pet_noted`).
   - Strict species compatibility enforced for `food`, `toy`, and `litter` (e.g., cat-only feather wands are never recommended as dog toys).
3. **Out-of-Stock (`stock_qty == 0`) & No-Match Handling**:
   - Matching SKUs with `stock_qty == 0` are recorded in `out_of_stock_names` and excluded from primary cards.
   - When zero primary in-stock SKUs match (e.g., `"dog toys under 300,000 VND"` when only cat toys are stocked), `no_primary_match = True` is set honestly and up to 3 in-stock adjacent products verified for the same species and budget are clearly badged `[Alternative]` / `[Thay thế]`.

### 2.3 Product Ranking Formula ($0..100$)
$$
S_{\text{prod}}(q) = S_{\text{species}}(q) + S_{\text{category}}(q) + S_{\text{stage\_weight}}(q) + S_{\text{budget\_unit}}(q) + S_{\text{stock}}(q)
$$
- `species_fit` (`0..30`), `category_subtopic_fit` (`0..25`), `life_stage_weight_fit` (`0..15`), `budget_unit_value` (`0..20`, rewarding best normalized unit cost within comparable groups), and `stock_health` (`0..10`, rewarding healthy stock above `reorder_level`).

---

## 3. Side-by-Side Product Comparison (`build_product_comparison`)

Supports `2–4` active tenant products resolved via:
1. Explicit SKU codes in the user prompt or Compare Tray (`Compare FOOD-001, FOOD-002, FOOD-006`), returning a targeted clarification if `< 2` valid active SKUs exist in the current tenant;
2. `session_state.last_recommended_product_ids` for contextual follow-ups (*"Compare these three products"*); or
3. Top-ranked category matches from `recommend_products`.

Outputs a `ComparisonTable` with 9 standardized rows (`code`, `category`, `price`, `package_size`, `unit_price`, `stock`, `species`, `life_stage`, `description`, `undocumented`) plus an automated value summary highlighting both lowest upfront price and lowest normalized unit cost. Rendered as a full comparison `<table>` on desktop and zero-overflow stacked `<dl>` cards at `<= 680px`.

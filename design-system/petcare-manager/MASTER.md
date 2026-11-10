# PetCare Manager — Design System

- **Product:** daily operations workspace for independent pet shops
- **Audience:** store owners and staff handling sales, stock, customers, pets, and reports
- **Stack:** Flask, Jinja2, vanilla JavaScript, hand-written CSS
- **Density:** compact, readable, task-first
- **Motion:** brief feedback only; reduced motion is respected

## Design direction

Use a calm, dependable shop-floor interface. Animal photography supplies warmth; the controls and data stay quiet and easy to scan. Green identifies the product and primary actions. Amber and red communicate attention and errors. Keep content left aligned and use consistent SVG icons.

The UI Pro Max catalog suggested a consumer storefront palette and a feature-showcase landing pattern. Those do not fit an authenticated operations dashboard, so the recommendation was narrowed to an existing light interface with a restrained retail palette and task-first layout. No external font or CSS framework is required.

## Color tokens

| Role | Value | Token | Use |
|---|---|---|---|
| Page canvas | `#F5F7F6` | `--color-canvas` | Main application background |
| Surface | `#FFFFFF` | `--color-surface` | Navigation, panels, controls |
| Primary text | `#202D2A` | `--color-ink` | Headings and important data |
| Strong labels | `#34463F` | `--color-ink-strong` | Form labels and row headings |
| Secondary text | `#58665E` | `--color-muted` | Supporting text |
| Brand | `#287A62` | `--color-brand` | Primary actions, charts, selected states |
| Brand strong | `#1F624F` | `--color-brand-strong` | Text links, hover, active navigation |
| Brand soft | `#E8F3ED` | `--color-brand-soft` | Selected surfaces and quiet icon backgrounds |
| Divider | `#E2E9E5` | `--color-border` | Panel edges and separators |
| Subtle divider | `#EDF1EE` | `--color-border-subtle` | Quiet internal separators |
| Attention text / surface | `#80511F` / `#FFF2DD` | `--color-warning` / `--color-warning-soft` | Low stock and pending states |
| Error text / surface | `#9A4C47` / `#FFF0ED` | `--color-danger` / `--color-danger-soft` | Failed actions and destructive outcomes |
| Positive text / surface | `#326B49` / `#E5F5EA` | `--color-positive` / `--color-positive-soft` | Completed and healthy states |

Normal text must remain at least 4.5:1 against its surface. Do not use color alone to communicate stock, invoice, or pet status.

## Type and spacing

- Use the system UI stack already bundled by the browser. Avoid a remote font dependency for the authenticated workspace.
- Use 28–36px for page titles, 17–20px for panel titles, 14–16px for body copy, and 12–13px only for supporting labels or dense table metadata.
- Use tabular numerals for money, counts, timestamps, and stock levels.
- Keep the existing 4/8px spacing rhythm. Standard controls and touch actions are at least 44px high.
- Use 8px control corners and 12–16px panel corners. Reserve shadows for layered or interactive surfaces.

## Layout

Desktop keeps the navigation stable and gives the current task the strongest visual position:

```text
┌───────────────┬──────────────────────────────────────────────────────┐
│ Store + nav   │ account / locale                                     │
│               ├──────────────────────────────────────────────────────┤
│ Main modules  │ page title                                  main CTA │
│               │ key measures across the page                        │
│ Tenant switch │ sales / stock / recent work in clear groups         │
└───────────────┴──────────────────────────────────────────────────────┘
```

Mobile moves the navigation to a safe-area-aware bottom bar and stacks the work in reading order:

```text
┌──────────────────────────────┐
│ brand     store / account    │
│ page title + primary action  │
│ measures in a 2 × 2 grid     │
│ task panels stacked          │
│                              │
├────── bottom navigation ─────┤
└──────────────────────────────┘
```

Tables may scroll inside their own labelled region; the page itself must not gain horizontal overflow. Long names and identifiers must wrap or expose a full-value path.

## Component rules

- **Navigation:** one active state, clear labels, visible keyboard focus, and no hover-only actions.
- **Primary action:** use for the page's main task (for example, creating or paying an invoice). Secondary actions use quiet surfaces.
- **Metrics:** share one neutral surface and type scale. Use semantic state colors only when a measure signals a real condition.
- **Forms:** visible labels, inline validation, retained values after failure, and explicit loading/success feedback.
- **Tables and lists:** align values by meaning, use tabular numbers, preserve readable row spacing, and provide helpful empty states.
- **Images:** keep the subject visible with `object-fit: cover`; reserve dimensions to prevent layout shift; provide meaningful alt text.
- **Icons:** use the existing SVG icon set. Hide decorative icons from assistive technology and label icon-only controls.
- **Feedback:** errors say what happened and how to recover. Destructive actions require confirmation or a reversible undo path.

## Motion and responsive behavior

- Transition only the properties needed: color, background, border, shadow, or transform. Never use `transition: all`.
- Keep hover feedback subtle and do not shift surrounding layout. Do not animate data into view before it can be read.
- Respect `prefers-reduced-motion`; all essential information and final states remain visible without animation.
- Review at 375px, 768px, 1024px, and 1440px. Keep bottom navigation, assistant overlays, and focused controls clear of device safe areas.

## Avoid

- Marketing hero patterns, promotional social proof, or oversized decorative metric cards in store operations pages.
- Unrelated pastel colors for metrics that have no status meaning.
- Emoji as navigation or action icons, external font requirements, gradients used only as decoration, and generic hover animation on every element.
- Changing store, invoice, stock, or tenant meaning in the browser; the server remains authoritative.

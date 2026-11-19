# AI Features & Local Vision Architecture (`AI_FEATURES.md`)

PetCare Manager integrates two complementary AI capabilities built with strict privacy, role-scoping, and offline-first fallback guarantees.

---

## 1. Conversational Shopping & Store Assistant

### 1.1 Internal AI Workspace (`/assistant/chat` & Topbar Drawer)
- **Store Mode (`workspace`)**: Role-scoped read-only assistant powered by real MySQL queries (`assistant_operations_service.py`, `restock_service.py`, `report_service.py`). Supports inventory forecasts (`target_days=14`), top-selling products (`week` / `month` / `today`), purchase-order summaries, operational overviews (Admin), product recommendations & side-by-side unit-price comparison tray, and pet attribute search.
- **Shopper Preview Mode (`shopper_preview`)**: Blocks internal store revenue, stock counts, and POs; restricts scope strictly to public retail catalog and veterinary knowledge base.
- **Veterinary Safety Guardrails**: Clinical emergencies (post-op wound dehiscence, breathing distress, poisoning, head-pressing) trigger structured `emergency` or `vet_referral` safety banners (`escalation_steps` + audited citations from WSAVA / AVMA / AAFP / ASPCA) and suppress retail shopping recommendations automatically (`0` cards). Duplicate plain-text bodies are deduplicated when already displayed inside `.ai-safety-banner`.

### 1.2 Customer Shopping AI (`/shop/ai-assistant`)
- Public-safe concierge scoped via `storefront_ai_service.py` to available pets, active products, and reviewed pet-care guidance.
- Never queries customer PII, private invoices, purchase orders, or internal audit logs.

### 1.3 Offline Python Engine vs External LLM Provider Fallback
- **Default (`AI_PROVIDER_APPROVED=0`)**: Runs 100% locally via deterministic Python NLU + parameterized MySQL queries — no external API keys required, zero outbound calls, honest diagnostic badge (`Offline Python Engine`).
- **Optional External Provider (`AI_PROVIDER=gemini` or OpenAI-compatible + `AI_PROVIDER_APPROVED=1` + `AI_TOOL_CALLING_ENABLED=1`)**: Calls `/v1/chat/completions` (or Google Gemini endpoint) with short history (`<= 8` turns) and relevant non-PII catalog snippets under strict rate limits (`AI_RATE_LIMIT_RPM`, `AI_RATE_LIMIT_TPM`, `AI_RATE_LIMIT_RPD`). Automatically falls back to the local Python engine on timeout/quota/provider error and visibly updates provenance labels on every message.

---

## 2. Local AI Vision 4.0 (`/pets/find-similar` & `/shop/image-search`)

Runs completely offline on CPU via `onnxruntime` using binaries verified in [`petcare/vision/models/MODEL_MANIFEST.json`](../petcare/vision/models/MODEL_MANIFEST.json):

| Model File | Role | Input Shape | SHA-256 |
|---|---|---|---|
| `yolox_nano.onnx` | Stage 1 object detector (filters cat/dog, rejects non-animal & multi-animal) | `[1, 3, 416, 416]` | `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d` |
| `mobilenetv2-12.onnx` | Stage 2 crop species verifier (118 dog breeds, 5 cat groups) | `[1, 3, 224, 224]` | `c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5` |
| `mobilenetv2-12-features.onnx` | Stage 2 dual-output species & `1280`-D foreground embedding extractor | `[batch, 3, 224, 224]` | `0a15a2be5af52322c7b00bfc62b10fce4e10270c3bd60feb6f9268fcb2820f88` |

### Key Pipeline & Security Controls
- Images (`<= 5 MB`, JPEG/PNG/WebP) are decoded safely, stripped of EXIF metadata, and never stored when submitted purely for search.
- Results prioritize SHA-256 byte-exact matches (if the exact stored photo is uploaded), otherwise rank same-species candidates using `1280`-D normalized embeddings + white-balanced CIE-Lab color histograms + multi-photo reference galleries (`pet_reference_photos`, up to 5 photos/pet).
- Uploaded preview (`matches.query_preview`) renders alongside heuristic scores formatted out of `/100` (not `%`).

### Honest AI Vision Limitations (Critical)
- **Visual similarity is NOT verified individual pet identity.** Two different photos of different animals of similar breed/color may rank near each other (`same_pet_multi_view_reidentification = NOT EVALUATED`). Staff must always confirm the physical animal before checkout/handover.
- **Verified vs Illustrative Photos**: Only uploaded/seeded synthetic pet portraits are stored in private media storage (`68` demo portraits in `assets/demo/pets/`). Profiles without photos show vector fallback artwork (`petcare/static/img/catalog/fallbacks/*.svg`) clearly labeled **"Minh họa" / "Illustrative"**.
- Optional external vision attribute extraction (`AI_VISION_ENABLED=1`) is disabled by default (`0`) and never auto-overwrites populated form fields.

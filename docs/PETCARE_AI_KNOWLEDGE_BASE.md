# PetCare AI — Trusted Pet-Care Knowledge Base & Veterinary Safety

## 1. Curated Corpus Design (`petcare/ai/knowledge_base.py`)

PetCare AI answers general dog and cat care questions exclusively from a versioned, human-reviewed bilingual (`vi`/`en`) corpus (`KNOWLEDGE_CORPUS`) rather than open-ended parametric generation.

Every `KnowledgeDocument` stores mandatory provenance metadata:
- `doc_id`: Immutable identifier (`KB-NUTR-001` .. `KB-VET-009`)
- `title_vi` / `title_en`: Localized article titles
- `source_name` & `source_url`: Authoritative veterinary/welfare body (`https://` only)
- `updated_at`, `topic`, `species_scope` (`cat` | `dog` | `both`), `review_status` (`"reviewed"`), and `version` (`"1.0.0"`)

### Reviewed Reference Corpus Summary

| `doc_id` | Topic | Species | Authoritative Source |
|---|---|---|---|
| `KB-NUTR-001` | `feeding_practices` | `both` | WSAVA Global Nutrition Guidelines (Life-stage meals & 7–10 day diet transition) |
| `KB-SAFE-002` | `feeding_practices` | `both` | ASPCA Animal Poison Control (Toxic household foods & plants: chocolate, xylitol, grapes, onions, lilies) |
| `KB-GROOM-003` | `grooming_basics` | `both` | AVMA Pet Care Guidelines (Coat brushing frequency, pH-balanced bathing, nails, enzymatic dental & ear care) |
| `KB-ENV-004` | `environmental_preparation` | `cat` | AAFP / ISFM Feline Environmental Needs Guidelines (Balcony mesh, decompression room & $N + 1$ litter box rule) |
| `KB-ENV-005` | `environmental_preparation` | `dog` | AVMA / Cornell Canine Care (Puppy-proofing, crate comfort, chew outlets & routine walks) |
| `KB-ENRICH-006` | `pet_enrichment` | `both` | AAFP & AVMA Behavioral Enrichment (Prey-sequence play for cats, sniffing/foraging & mental stimulation for dogs) |
| `KB-BEHAV-007` | `basic_behavior` | `both` | Cornell Feline & Canine Behavior (Positive reinforcement, scratching post placement, avoiding punishment) |
| `KB-OWN-008` | `responsible_ownership` | `both` | WSAVA / AVMA Responsible Pet Ownership (10–15+ year commitment, preventive vet visits, budget planning) |
| `KB-VET-009` | `emergency_triage` | `both` | AVMA Veterinary Emergency Triage (Red-flag respiratory, neurological, GI, urinary & toxin warning signs) |

---

## 2. Pure-Python Okapi BM25 + Bigram Retrieval

Because the curated reference corpus is compact, domain-focused, and bilingual, **Okapi BM25 over normalized unigrams + bigrams** provides sub-millisecond latency, exact keyword explainability, zero external vector-DB or embedding API dependencies, and deterministic reproducibility.

For query $Q$ with unique normalized tokens/bigrams $q_1, \dots, q_m$ and document $D$:

$$
\text{BM25}(Q, D) = \sum_{i=1}^{m} \text{IDF}(q_i) \cdot \frac{f(q_i, D)\cdot (k_1 + 1)}{f(q_i, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}
$$

where:
- $\text{IDF}(q_i) = \ln\left(1 + \frac{N - n(q_i) + 0.5}{n(q_i) + 0.5}\right)$
- $k_1 = 1.5$, $b = 0.75$, curated `keywords` receive a $2\times$ field boost, and `species_hint` applies a $1.15\times$ boost to matching species documents ($0.65\times$ to opposite-species-only documents).
- **Confidence Threshold**: Documents must achieve $\text{score} \ge \text{MIN\_BM25\_SCORE} = 2.2$.
- **Exotic Species Guard**: Word-boundary detection (`\b(?:iguana|reptiles?|snakes?|turtles?|parrots?|hamsters?|rabbits?|...)\b`) clears hits for non-dog/cat animals so PetCare AI states honestly that its reviewed corpus covers dogs and cats only—without false substring collisions on words like `"transition"` or Vietnamese `"răng"`.

---

## 3. Three-Tier Veterinary Safety & Medical Guardrails

PetCare AI never presents itself as a licensed veterinarian:

1. **Tier 1 — Urgent Emergency Escalation (`severity="emergency"`, `role="alert"`)**:
   - Triggered immediately on red-flag phrases: labored/open-mouth breathing (`khó thở`, `thở gấp`), seizures/collapse (`co giật`, `ngất`), bloody vomiting/diarrhea (`nôn ra máu`), urinary blockage (`bí tiểu`, `rặn tiểu`), bloated hard abdomen, or toxin ingestion (`chocolate`, `xylitol`, `lily leaf` / `hoa ly`, `nho khô`, `paracetamol`, `ibuprofen`, `bả chuột`).
   - Bypasses shopping flows and renders a high-contrast emergency alert instructing immediate transport to a veterinary clinic, never advising home emesis or human drugs.
2. **Tier 2 — Medical Diagnosis & Dosage Refusal (`severity="medical_boundary"`)**:
   - Intercepts requests for clinical diagnosis (*"chẩn đoán bệnh gì"*), prescriptions, antibiotics, or `mg/kg` medication dosages (*"amoxicillin dosage for 6 kg dog"*), declining safely and recommending a licensed veterinarian.
3. **Tier 3 — Mandatory Reference Disclaimer (`severity="disclaimer"`)**:
   - Attached to every general care `knowledge_answer` alongside clickable `https://` source citation cards (`rel="noopener noreferrer"`).

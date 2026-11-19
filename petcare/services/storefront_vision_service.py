"""Public storefront AI-4.0 image search wrapper with strict DTO scrubbing."""

from __future__ import annotations

from petcare.database.connection import read_connection, set_tenant_context
from petcare.repositories import storefront_repo
from petcare.services import pet_image_service


def search_public_pets_by_image(tenant_id: int, image_bytes: bytes, species: str = "") -> dict:
    """Run local AI-4.0 matching on available public pets and strip internal descriptors/PII."""
    clean_species = (species or "").strip()[:80]
    if clean_species.lower() not in {"", "cat", "dog", "mèo", "chó"}:
        clean_species = ""

    raw = pet_image_service.search_similar_for_storefront(
        tenant_id,
        image_bytes,
        species=clean_species,
        include_similar=True,
    )

    raw_results = raw.get("results") or []
    matched_ids = [int(item["pet"]["id"]) for item in raw_results if item.get("pet")]
    reserved_ids: set[int] = set()
    if matched_ids:
        with read_connection() as connection:
            set_tenant_context(connection, tenant_id)
            reserved_ids = storefront_repo.locked_pet_ids(connection, matched_ids)

    public_results = []
    for item in raw_results:
        pet = item.get("pet") or {}
        if pet.get("sale_status") not in (None, "available"):
            continue
        pet_id = int(pet["id"])
        public_pet = {
            "id": pet_id,
            "code": pet.get("code"),
            "name": pet.get("name"),
            "species": pet.get("species"),
            "breed": pet.get("breed") or "",
            "coat_color": pet.get("coat_color") or "",
            "eye_color": pet.get("eye_color") or "",
            "sale_price": pet.get("sale_price"),
            "sale_status": "available",
            "photo_filename": pet.get("photo_filename"),
            "is_reserved": pet_id in reserved_ids,
        }
        public_results.append({
            "pet": public_pet,
            "score": int(item.get("score") or 0),
            "match_tier": item.get("match_tier") or "visually_similar_candidate",
            "identity_decision": item.get("identity_decision") or "visually_similar_pet",
            "potential_same_pet_review": bool(item.get("potential_same_pet_review")),
            "reasons": list(item.get("reasons") or []),
        })

    return {
        "results": public_results,
        "match_outcome": raw.get("match_outcome"),
        "abstention_reason": raw.get("abstention_reason"),
        "verified_species": raw.get("verified_species"),
        "verified_species_source": raw.get("verified_species_source"),
        "subject_status": raw.get("subject_status"),
        "query_preview": raw.get("query_preview"),
    }


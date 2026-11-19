import json

from petcare.repositories.base import contains_filter, execute, fetch_all, fetch_one
from petcare.vision.image_features import (
    VISUAL_HASH_BITS,
    VISUAL_HASH_VERSION,
    descriptor_from_json,
    visual_hash_bands,
)


PHOTO_HASH_VERSION = VISUAL_HASH_VERSION
PHOTO_HASH_BAND_COUNT = VISUAL_HASH_BITS // 8
MAX_IMAGE_SEARCH_CANDIDATES = 5000
MAX_PET_GALLERY_PHOTOS = 5
VALID_IMAGE_ROLES = (
    "additional",
    "front_view",
    "side_view",
    "coat_detail",
    "lighting_variant",
    "face_closeup",
    "full_body",
)
_PHOTO_HASH_RE = "^[0-9a-fA-F]{16}$"


def _attach_reference_photos_batch(connection, rows):
    """Attach ordered ``reference_photos`` lists to a batch of pet rows in one query."""
    if not rows:
        return rows
    pet_ids = [int(r["id"]) for r in rows if r.get("id") is not None]
    if not pet_ids:
        return rows
    marks = ", ".join(["%s"] * len(pet_ids))
    ref_rows = fetch_all(
        connection,
        # B608: placeholder count only; all pet_ids are bound integers.
        "SELECT id, pet_id, photo_filename, photo_descriptor, image_role, sort_order "  # nosec B608
        f"FROM pet_reference_photos WHERE tenant_id = @petcare_tenant_id AND pet_id IN ({marks}) "
        "ORDER BY pet_id, sort_order, id",
        tuple(pet_ids),
    )
    by_pet: dict[int, list[dict]] = {}
    for ref in ref_rows:
        by_pet.setdefault(int(ref["pet_id"]), []).append(ref)
    for row in rows:
        row["reference_photos"] = by_pet.get(int(row["id"]), [])
    return rows


def list_pets(connection, search="", status=""):
    search_sql, search_params = contains_filter(search, "p.code", "p.name", "p.species")
    where_status = "AND p.sale_status = %s" if status else ""
    params = list(search_params)
    if status:
        params.append(status)
    return fetch_all(
        connection,
        "SELECT p.*, c.full_name buyer_name FROM pets p "
        "LEFT JOIN customers c ON c.id = p.buyer_id AND c.tenant_id = p.tenant_id "
        "WHERE p.tenant_id = @petcare_tenant_id "
        + search_sql + " " + where_status
        + " ORDER BY FIELD(p.sale_status, 'available', 'sold', 'inactive'), p.name, p.id",
        tuple(params),
    )


def iter_available_for_image_search(connection, batch_size=250):
    """Stream only fields needed for image ranking in bounded MySQL batches."""
    batch_size = max(1, min(int(batch_size), 1000))
    cursor = connection.cursor(dictionary=True, buffered=False)
    try:
        cursor.execute(
            "SELECT p.id, p.code, p.name, p.species, p.breed, p.coat_color, "
            "p.eye_color, p.appearance_tags, p.photo_filename, p.photo_descriptor, p.sale_price "
            "FROM pets p WHERE p.tenant_id = @petcare_tenant_id "
            "AND p.sale_status = 'available' ORDER BY p.id"
        )
        while rows := cursor.fetchmany(batch_size):
            yield from _attach_reference_photos_batch(connection, rows)
    finally:
        cursor.close()


def has_available_reference_photos(connection):
    return fetch_one(
        connection,
        "SELECT 1 found FROM pets p WHERE p.tenant_id = @petcare_tenant_id "
        "AND p.sale_status = 'available' AND (p.photo_filename IS NOT NULL OR "
        "EXISTS (SELECT 1 FROM pet_reference_photos rp "
        "WHERE rp.tenant_id = p.tenant_id AND rp.pet_id = p.id)) LIMIT 1",
    ) is not None


def count_available_for_image_search(connection):
    """Return the current tenant's available pet count for an exact-scan decision."""
    row = fetch_one(
        connection,
        "SELECT COUNT(*) AS pet_count FROM pets "
        "WHERE tenant_id = @petcare_tenant_id AND sale_status = 'available'",
    )
    return int(row["pet_count"]) if row else 0


def find_available_image_search_candidates(
    connection, visual_hash, max_candidates=MAX_IMAGE_SEARCH_CANDIDATES
):
    """Return indexed and legacy candidates, or None when a full scan is safer.

    Each byte-sized LSH band probes its exact bucket and all one-bit neighbors.
    This retrieves every descriptor within Hamming distance eight while keeping
    the common-case candidate set much smaller than the full tenant catalog.
    """
    bands = visual_hash_bands(visual_hash)
    if bands is None:
        return None
    max_candidates = max(1, min(int(max_candidates), 10_000))
    bucket_probes = []
    for band_index, bucket in enumerate(bands):
        bucket_probes.extend(
            {"band": band_index, "bucket_value": bucket ^ bit_mask}
            for bit_mask in (0, *(1 << bit for bit in range(8)))
        )
    probe_json = json.dumps(bucket_probes, separators=(",", ":"))
    candidate_ids = fetch_all(
        connection,
        "SELECT DISTINCT l.pet_id "
        "FROM JSON_TABLE(%s, '$[*]' COLUMNS (band TINYINT UNSIGNED PATH '$.band', "
        "bucket_value TINYINT UNSIGNED PATH '$.bucket_value')) AS probe "
        "JOIN pet_photo_lsh l FORCE INDEX (idx_pet_photo_lsh_bucket) "
        "ON l.tenant_id = @petcare_tenant_id AND l.hash_version = %s "
        "AND l.band = probe.band AND l.bucket_value = probe.bucket_value "
        "JOIN pets p ON p.tenant_id = l.tenant_id AND p.id = l.pet_id "
        "WHERE p.sale_status = 'available' LIMIT %s",
        (probe_json, PHOTO_HASH_VERSION, max_candidates + 1),
    )
    ids = [int(row["pet_id"]) for row in candidate_ids]
    if len(ids) > max_candidates:
        return None

    remaining = max_candidates - len(ids)
    legacy = fetch_all(
        connection,
        "SELECT p.id, p.code, p.name, p.species, p.breed, p.coat_color, "
        "p.eye_color, p.appearance_tags, p.photo_filename, p.photo_descriptor, p.sale_price "
        "FROM pets p WHERE p.tenant_id = @petcare_tenant_id "
        "AND p.sale_status = 'available' AND (p.photo_descriptor IS NULL OR "
        "COALESCE(JSON_UNQUOTE(JSON_EXTRACT(p.photo_descriptor, '$.visual_hash')), '') "
        "NOT REGEXP %s) ORDER BY p.id LIMIT %s",
        (_PHOTO_HASH_RE, remaining + 1),
    )
    if len(legacy) > remaining:
        return None

    indexed = []
    if ids:
        pet_ids_json = json.dumps(ids, separators=(",", ":"))
        indexed = fetch_all(
            connection,
            "SELECT p.id, p.code, p.name, p.species, p.breed, p.coat_color, "
            "p.eye_color, p.appearance_tags, p.photo_filename, p.photo_descriptor, p.sale_price "
            "FROM JSON_TABLE(%s, '$[*]' COLUMNS (pet_id BIGINT UNSIGNED PATH '$')) AS candidate "
            "STRAIGHT_JOIN pets p ON p.id = candidate.pet_id "
            "WHERE p.tenant_id = @petcare_tenant_id AND p.sale_status = 'available' ORDER BY p.id",
            (pet_ids_json,),
        )
    combined = sorted((*legacy, *indexed), key=lambda pet: int(pet["id"]))
    return _attach_reference_photos_batch(connection, combined)


def replace_photo_search_index(connection, tenant_id, pet_id, descriptor_json):
    """Replace derived SimHash bands in the same transaction as the pet photo."""
    replace_photo_search_indexes(
        connection, ((tenant_id, pet_id, descriptor_json),)
    )


def replace_photo_search_indexes(connection, pet_descriptors):
    """Batch-replace derived bands after primary or gallery descriptor updates."""
    pet_descriptors = tuple(pet_descriptors)
    if not pet_descriptors:
        return
    cursor = connection.cursor()
    try:
        cursor.executemany(
            "DELETE FROM pet_photo_lsh WHERE tenant_id = %s AND pet_id = %s",
            [(tenant_id, pet_id) for tenant_id, pet_id, _ in pet_descriptors],
        )
        seen_buckets: set[tuple[int, int, int, int, int]] = set()
        buckets = []
        for tenant_id, pet_id, descriptor_payload in pet_descriptors:
            if isinstance(descriptor_payload, (list, tuple)):
                raw_list = descriptor_payload
            else:
                raw_list = (descriptor_payload,) if descriptor_payload else ()
            for raw_json in raw_list:
                descriptor = descriptor_from_json(raw_json)
                bands = visual_hash_bands(descriptor.visual_hash) if descriptor else None
                if bands and len(bands) == PHOTO_HASH_BAND_COUNT:
                    for band, bucket in enumerate(bands):
                        entry = (int(tenant_id), int(pet_id), PHOTO_HASH_VERSION, band, bucket)
                        if entry not in seen_buckets:
                            seen_buckets.add(entry)
                            buckets.append(entry)
        if buckets:
            cursor.executemany(
                "INSERT INTO pet_photo_lsh "
                "(tenant_id, pet_id, hash_version, band, bucket_value) "
                "VALUES (%s, %s, %s, %s, %s)",
                buckets,
            )
    finally:
        cursor.close()


def sync_pet_gallery_search_index(connection, pet_id):
    """Rebuild LSH buckets across a pet's primary photo and all verified reference photos."""
    tenant_row = fetch_one(connection, "SELECT @petcare_tenant_id tenant_id")
    if not tenant_row or not tenant_row["tenant_id"]:
        return
    tenant_id = int(tenant_row["tenant_id"])
    pet_row = fetch_one(
        connection,
        "SELECT photo_descriptor FROM pets WHERE id = %s AND tenant_id = @petcare_tenant_id",
        (pet_id,),
    )
    ref_rows = fetch_all(
        connection,
        "SELECT photo_descriptor FROM pet_reference_photos "
        "WHERE tenant_id = @petcare_tenant_id AND pet_id = %s ORDER BY sort_order, id",
        (pet_id,),
    )
    descriptors = []
    if pet_row and pet_row.get("photo_descriptor"):
        descriptors.append(pet_row["photo_descriptor"])
    descriptors.extend(r["photo_descriptor"] for r in ref_rows if r.get("photo_descriptor"))
    replace_photo_search_indexes(connection, ((tenant_id, pet_id, descriptors),))


def count_pets(connection, search="", status=""):
    search_sql, search_params = contains_filter(search, "code", "name", "species")
    where_status = "AND sale_status = %s" if status else ""
    params = list(search_params)
    if status:
        params.append(status)
    return fetch_one(
        connection,
        "SELECT COUNT(*) total FROM pets WHERE tenant_id = @petcare_tenant_id "
        + search_sql + " " + where_status,
        tuple(params),
    )["total"]


def list_pets_page(connection, search="", status="", limit=25, offset=0):
    search_sql, search_params = contains_filter(search, "p.code", "p.name", "p.species")
    where_status = "AND p.sale_status = %s" if status else ""
    params = list(search_params)
    if status:
        params.append(status)
    params.extend((limit, offset))
    return fetch_all(
        connection,
        "SELECT p.*, c.full_name buyer_name FROM pets p "
        "LEFT JOIN customers c ON c.id = p.buyer_id AND c.tenant_id = p.tenant_id "
        "WHERE p.tenant_id = @petcare_tenant_id "
        + search_sql + " "
        + where_status + " ORDER BY FIELD(p.sale_status, 'available', 'sold', 'inactive'), "
        "p.name, p.id LIMIT %s OFFSET %s",
        tuple(params),
    )


def get_pet(connection, pet_id, lock=False):
    suffix = " FOR UPDATE" if lock else ""
    return fetch_one(
        connection,
        "SELECT p.*, c.full_name buyer_name FROM pets p "
        "LEFT JOIN customers c ON c.id = p.buyer_id AND c.tenant_id = p.tenant_id "
        "WHERE p.id = %s AND p.tenant_id = @petcare_tenant_id" + suffix,
        (pet_id,),
    )


def get_pets_by_ids(connection, pet_ids, lock=False):
    """Read a stable, tenant-scoped pet set for atomic invoice/refund workflows."""
    pet_ids = sorted(set(pet_ids))
    if not pet_ids:
        return []
    placeholders = ", ".join(["%s"] * len(pet_ids))
    suffix = " FOR UPDATE" if lock else ""
    return fetch_all(
        connection,
        "SELECT id, sale_status, buyer_id FROM pets "
        "WHERE tenant_id = @petcare_tenant_id "
        f"AND id IN ({placeholders}) ORDER BY id{suffix}",
        tuple(pet_ids),
    )


def mark_sold(connection, pet_id, customer_id):
    return execute(
        connection,
        "UPDATE pets SET sale_status = 'sold', buyer_id = %s, sold_at = NOW() "
        "WHERE id = %s AND tenant_id = @petcare_tenant_id "
        "AND sale_status = 'available'",
        (customer_id, pet_id),
    )[1]


def has_photo(connection, filename):
    return fetch_one(
        connection,
        "SELECT 1 found FROM pets WHERE tenant_id = @petcare_tenant_id AND photo_filename = %s "
        "UNION ALL "
        "SELECT 1 found FROM pet_reference_photos WHERE tenant_id = @petcare_tenant_id AND photo_filename = %s "
        "LIMIT 1",
        (filename, filename),
    ) is not None


def count_photo_references(connection, filename):
    """Count all primary and gallery references before removing a stored media object."""
    return int(
        fetch_one(
            connection,
            "SELECT (SELECT COUNT(*) FROM pets WHERE photo_filename = %s) + "
            "(SELECT COUNT(*) FROM pet_reference_photos WHERE photo_filename = %s) AS total",
            (filename, filename),
        )["total"]
    )


def list_reference_photos(connection, pet_id):
    return fetch_all(
        connection,
        "SELECT id, tenant_id, pet_id, photo_filename, photo_descriptor, image_role, "
        "sort_order, created_at, updated_at FROM pet_reference_photos "
        "WHERE tenant_id = @petcare_tenant_id AND pet_id = %s ORDER BY sort_order, id",
        (pet_id,),
    )


def get_reference_photo(connection, pet_id, photo_id, lock=False):
    suffix = " FOR UPDATE" if lock else ""
    return fetch_one(
        connection,
        "SELECT id, tenant_id, pet_id, photo_filename, photo_descriptor, image_role, sort_order "
        "FROM pet_reference_photos WHERE tenant_id = @petcare_tenant_id AND pet_id = %s AND id = %s"
        + suffix,
        (pet_id, photo_id),
    )


def count_reference_photos(connection, pet_id):
    row = fetch_one(
        connection,
        "SELECT COUNT(*) AS cnt FROM pet_reference_photos "
        "WHERE tenant_id = @petcare_tenant_id AND pet_id = %s",
        (pet_id,),
    )
    return int(row["cnt"]) if row else 0


def add_reference_photo(connection, pet_id, photo_filename, photo_descriptor, image_role, sort_order):
    ref_id = execute(
        connection,
        "INSERT INTO pet_reference_photos "
        "(tenant_id, pet_id, photo_filename, photo_descriptor, image_role, sort_order) "
        "VALUES (@petcare_tenant_id, %s, %s, %s, %s, %s)",
        (pet_id, photo_filename, photo_descriptor, image_role, sort_order),
    )[0]
    sync_pet_gallery_search_index(connection, pet_id)
    return ref_id


def resequence_reference_photos(connection, pet_id, ordered_ids):
    cursor = connection.cursor()
    try:
        for idx, ref_id in enumerate(ordered_ids, start=1):
            cursor.execute(
                "UPDATE pet_reference_photos SET sort_order = %s "
                "WHERE tenant_id = @petcare_tenant_id AND pet_id = %s AND id = %s",
                (idx, pet_id, ref_id),
            )
    finally:
        cursor.close()


def delete_reference_photo(connection, pet_id, photo_id):
    deleted = execute(
        connection,
        "DELETE FROM pet_reference_photos "
        "WHERE tenant_id = @petcare_tenant_id AND pet_id = %s AND id = %s",
        (pet_id, photo_id),
    )[1]
    if deleted:
        remaining = list_reference_photos(connection, pet_id)
        resequence_reference_photos(connection, pet_id, [r["id"] for r in remaining])
        sync_pet_gallery_search_index(connection, pet_id)
    return deleted


def swap_primary_with_reference_photo(connection, pet_id, photo_id, current_primary_filename, current_primary_descriptor):
    ref_row = get_reference_photo(connection, pet_id, photo_id, lock=True)
    if not ref_row:
        return False
    updated = execute(
        connection,
        "UPDATE pets SET photo_filename = %s, photo_descriptor = %s "
        "WHERE id = %s AND tenant_id = @petcare_tenant_id "
        "AND sale_status IN ('available', 'inactive')",
        (ref_row["photo_filename"], ref_row["photo_descriptor"], pet_id),
    )[1]
    if not updated:
        return False
    if current_primary_filename and current_primary_descriptor:
        execute(
            connection,
            "UPDATE pet_reference_photos SET photo_filename = %s, photo_descriptor = %s "
            "WHERE id = %s AND pet_id = %s AND tenant_id = @petcare_tenant_id",
            (current_primary_filename, current_primary_descriptor, photo_id, pet_id),
        )
    else:
        execute(
            connection,
            "DELETE FROM pet_reference_photos WHERE id = %s AND pet_id = %s AND tenant_id = @petcare_tenant_id",
            (photo_id, pet_id),
        )
        remaining = list_reference_photos(connection, pet_id)
        resequence_reference_photos(connection, pet_id, [r["id"] for r in remaining])
    sync_pet_gallery_search_index(connection, pet_id)
    return True


def set_primary_photo(connection, pet_id, photo_filename, photo_descriptor):
    """Attach a primary photo to an available or inactive 0-photo pet and sync its gallery index."""
    changed = execute(
        connection,
        "UPDATE pets SET photo_filename = %s, photo_descriptor = %s "
        "WHERE id = %s AND tenant_id = @petcare_tenant_id "
        "AND sale_status IN ('available', 'inactive')",
        (photo_filename, photo_descriptor, pet_id),
    )[1]
    if changed:
        sync_pet_gallery_search_index(connection, pet_id)
    return changed


def create_pet(connection, data):
    pet_id = execute(
        connection,
        "INSERT INTO pets (tenant_id, code, name, species, breed, sex, birth_date, weight_kg, "
        "coat_color, eye_color, appearance_tags, photo_filename, photo_descriptor, sale_price, sale_price_vnd) "
        "VALUES (@petcare_tenant_id, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            data["code"], data["name"], data["species"], data["breed"], data["sex"],
            data["birth_date"], data["weight_kg"], data["coat_color"], data["eye_color"],
            data["appearance_tags"], data.get("photo_filename"),
            data.get("photo_descriptor"), data["sale_price"], data["legacy_sale_price_vnd"],
        ),
    )[0]
    if data.get("photo_descriptor"):
        tenant = fetch_one(connection, "SELECT @petcare_tenant_id tenant_id")
        if tenant and tenant["tenant_id"]:
            replace_photo_search_index(
                connection, tenant["tenant_id"], pet_id, data["photo_descriptor"]
            )
    return pet_id


def update_pet(connection, pet_id, data):
    changed = execute(
        connection,
        "UPDATE pets SET code = %s, name = %s, species = %s, breed = %s, sex = %s, "
        "birth_date = %s, weight_kg = %s, coat_color = %s, eye_color = %s, "
        "appearance_tags = %s, photo_filename = %s, photo_descriptor = %s, sale_price = %s, sale_price_vnd = %s "
        "WHERE id = %s AND tenant_id = @petcare_tenant_id AND sale_status = 'available'",
        (
            data["code"], data["name"], data["species"], data["breed"], data["sex"],
            data["birth_date"], data["weight_kg"], data["coat_color"], data["eye_color"],
            data["appearance_tags"], data.get("photo_filename"),
            data.get("photo_descriptor"), data["sale_price"], data["legacy_sale_price_vnd"], pet_id,
        ),
    )[1]
    if changed:
        sync_pet_gallery_search_index(connection, pet_id)
    return changed


def set_inactive(connection, pet_id, inactive):
    target = "inactive" if inactive else "available"
    return execute(
        connection,
        "UPDATE pets SET sale_status = %s WHERE id = %s "
        "AND tenant_id = @petcare_tenant_id AND sale_status IN ('available', 'inactive')",
        (target, pet_id),
    )[1]


def return_sold_pet(connection, pet_id, customer_id, sale_status):
    """Clear sold ownership after a returned pet is checked back into the store."""
    return execute(
        connection,
        "UPDATE pets SET sale_status = %s, buyer_id = NULL, sold_at = NULL "
        "WHERE id = %s AND tenant_id = @petcare_tenant_id "
        "AND sale_status = 'sold' AND buyer_id = %s",
        (sale_status, pet_id, customer_id),
    )[1]


def iter_filtered_for_image_search(connection, species="", status="available", batch_size=250):
    from petcare.vision.species_taxonomy import sql_species_aliases

    aliases = sql_species_aliases(species) if species else ("",) * 7
    cursor = connection.cursor(dictionary=True, buffered=False)
    try:
        cursor.execute("SELECT id, code, name, species, breed, coat_color, eye_color, appearance_tags, "
                       "sale_status, photo_filename, photo_descriptor, sale_price FROM pets "
                       "WHERE tenant_id = @petcare_tenant_id "
                       "AND (%s = '' OR species COLLATE utf8mb4_0900_ai_ci IN (%s, %s, %s, %s, %s, %s, %s)) "
                       "AND (%s = '' OR sale_status = %s) ORDER BY id", (species, *aliases, status, status))
        while rows := cursor.fetchmany(max(1, min(batch_size, 1000))):
            yield from _attach_reference_photos_batch(connection, rows)
    finally:
        cursor.close()

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
_PHOTO_HASH_RE = "^[0-9a-fA-F]{16}$"


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
            yield from rows
    finally:
        cursor.close()


def has_available_reference_photos(connection):
    return fetch_one(
        connection,
        "SELECT 1 found FROM pets WHERE tenant_id = @petcare_tenant_id "
        "AND sale_status = 'available' AND photo_filename IS NOT NULL LIMIT 1",
    ) is not None


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
    return sorted((*legacy, *indexed), key=lambda pet: int(pet["id"]))


def replace_photo_search_index(connection, tenant_id, pet_id, descriptor_json):
    """Replace derived SimHash bands in the same transaction as the pet photo."""
    replace_photo_search_indexes(
        connection, ((tenant_id, pet_id, descriptor_json),)
    )


def replace_photo_search_indexes(connection, pet_descriptors):
    """Batch-replace derived bands after descriptor backfills."""
    pet_descriptors = tuple(pet_descriptors)
    if not pet_descriptors:
        return
    cursor = connection.cursor()
    try:
        cursor.executemany(
            "DELETE FROM pet_photo_lsh WHERE tenant_id = %s AND pet_id = %s",
            [(tenant_id, pet_id) for tenant_id, pet_id, _ in pet_descriptors],
        )
        buckets = []
        for tenant_id, pet_id, descriptor_json in pet_descriptors:
            descriptor = descriptor_from_json(descriptor_json)
            bands = visual_hash_bands(descriptor.visual_hash) if descriptor else None
            if bands and len(bands) == PHOTO_HASH_BAND_COUNT:
                buckets.extend(
                    (tenant_id, pet_id, PHOTO_HASH_VERSION, band, bucket)
                    for band, bucket in enumerate(bands)
                )
        if buckets:
            cursor.executemany(
                "INSERT INTO pet_photo_lsh "
                "(tenant_id, pet_id, hash_version, band, bucket_value) "
                "VALUES (%s, %s, %s, %s, %s)",
                buckets,
            )
    finally:
        cursor.close()


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


def has_photo(connection, filename):
    return fetch_one(
        connection,
        "SELECT 1 found FROM pets WHERE tenant_id = @petcare_tenant_id "
        "AND photo_filename = %s LIMIT 1",
        (filename,),
    ) is not None


def count_photo_references(connection, filename):
    """Count all tenant references before removing a shared legacy object."""
    return fetch_one(
        connection,
        "SELECT COUNT(*) total FROM pets WHERE photo_filename = %s",
        (filename,),
    )["total"]


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
        tenant = fetch_one(connection, "SELECT @petcare_tenant_id tenant_id")
        if tenant:
            replace_photo_search_index(
                connection, tenant["tenant_id"], pet_id, data.get("photo_descriptor")
            )
    return changed


def set_inactive(connection, pet_id, inactive):
    target = "inactive" if inactive else "available"
    return execute(
        connection,
        "UPDATE pets SET sale_status = %s WHERE id = %s "
        "AND tenant_id = @petcare_tenant_id AND sale_status IN ('available', 'inactive')",
        (target, pet_id),
    )[1]

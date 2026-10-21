"""Safe local storage for pet photos and their reusable descriptors."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from uuid import uuid4

from petcare.vision.image_features import (
    ImageDescriptor,
    describe_image,
    descriptor_to_json,
    normalize_image_bytes,
    read_upload,
)
from petcare.vision.media_storage import LocalMediaStorage


SAFE_PHOTO_NAME = re.compile(r"^(?:t[1-9][0-9]{0,19}-)?[a-f0-9]{32}\.jpg$")


@dataclass(frozen=True, slots=True)
class StoredPhoto:
    filename: str
    descriptor: ImageDescriptor
    descriptor_json: str


@dataclass(frozen=True, slots=True)
class StoredImage:
    filename: str


def _save_normalized_image(
    normalized: bytes, image_dir: str | Path, tenant_id: int | None = None
) -> str:
    if tenant_id is not None:
        if isinstance(tenant_id, bool) or not isinstance(tenant_id, int) or tenant_id <= 0:
            raise ValueError("A valid tenant ID is required for scoped media.")
        filename = f"t{tenant_id}-{uuid4().hex}.jpg"
    else:
        filename = f"{uuid4().hex}.jpg"
    storage = image_dir if hasattr(image_dir, "put") else LocalMediaStorage(image_dir)
    storage.put(filename, normalized)
    return filename


def ensure_private_photo_directory(image_dir: str | Path) -> Path:
    directory = Path(image_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        # Photos can contain personal data; the tenant-shared volume must be
        # readable only by the application account.
        directory.chmod(0o700)
    return directory


def secure_existing_photos(image_dir: str | Path) -> int:
    """Tighten permissions on UUID photos, including tenant-prefixed names."""
    directory = ensure_private_photo_directory(image_dir)
    if os.name != "posix":
        return 0
    secured = 0
    for entry in directory.iterdir():
        if SAFE_PHOTO_NAME.fullmatch(entry.name) and not entry.is_symlink() and entry.is_file():
            entry.chmod(0o600)
            secured += 1
    return secured


def store_pet_photo(
    upload, image_dir: str | Path, max_bytes: int, tenant_id: int | None = None
) -> StoredPhoto:
    """Validate and re-encode a user upload, stripping metadata and its name."""
    data = read_upload(upload.stream, max_bytes)
    normalized = normalize_image_bytes(data)
    descriptor = describe_image(normalized)

    filename = _save_normalized_image(normalized, image_dir, tenant_id)
    return StoredPhoto(filename, descriptor, descriptor_to_json(descriptor))


def store_product_photo(
    upload, image_dir: str | Path, max_bytes: int, tenant_id: int | None = None
) -> StoredImage:
    """Validate and normalize a product photo, stripping metadata and its name."""
    data = read_upload(upload.stream, max_bytes)
    normalized = normalize_image_bytes(data)
    return StoredImage(_save_normalized_image(normalized, image_dir, tenant_id))


def remove_pet_photo(filename: str | None, image_dir: str | Path) -> None:
    if not filename:
        return
    storage = image_dir if hasattr(image_dir, "delete") else LocalMediaStorage(image_dir)
    storage.delete(filename)

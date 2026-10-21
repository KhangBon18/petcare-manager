"""Tighten filesystem permissions on legacy local pet and product photos."""

from petcare.config import Config
from petcare.vision.photo_storage import secure_existing_photos


def main():
    if Config.MEDIA_STORAGE_BACKEND != "local":
        raise SystemExit(
            "This command only applies to local filesystem photos; object-store permissions are managed by the provider."
        )
    for label, image_dir in (
        ("pet", Config.PET_IMAGE_DIR),
        ("product", Config.PRODUCT_IMAGE_DIR),
    ):
        secured = secure_existing_photos(image_dir)
        print(f"{label}: secured {secured} photo file(s) in {image_dir}")


if __name__ == "__main__":
    main()

import io
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from petcare.vision.photo_storage import (
    secure_existing_photos,
    store_pet_photo,
    store_product_photo,
)


def png_bytes():
    output = io.BytesIO()
    Image.new("RGB", (32, 32), (86, 142, 111)).save(output, format="PNG")
    return output.getvalue()


@unittest.skipUnless(os.name == "posix", "POSIX file modes are not portable to Windows.")
class PhotoStoragePermissionTests(unittest.TestCase):
    def test_pet_and_product_photos_use_private_directory_and_files(self):
        with tempfile.TemporaryDirectory() as root:
            image_dir = Path(root) / "photos"
            pet = store_pet_photo(
                SimpleNamespace(stream=io.BytesIO(png_bytes())), image_dir, 1024 * 1024
            )
            product = store_product_photo(
                SimpleNamespace(stream=io.BytesIO(png_bytes())), image_dir, 1024 * 1024
            )

            self.assertEqual(stat.S_IMODE(image_dir.stat().st_mode), 0o700)
            for filename in (pet.filename, product.filename):
                with self.subTest(filename=filename):
                    self.assertEqual(
                        stat.S_IMODE((image_dir / filename).stat().st_mode), 0o600
                    )

    def test_existing_photo_permissions_can_be_hardened_without_touching_other_files(self):
        with tempfile.TemporaryDirectory() as root:
            image_dir = Path(root) / "photos"
            image_dir.mkdir(mode=0o755)
            old_photo = image_dir / ("a" * 32 + ".jpg")
            unrelated = image_dir / "notes.txt"
            old_photo.write_bytes(b"photo")
            unrelated.write_text("keep mode", encoding="utf-8")
            image_dir.chmod(0o755)
            old_photo.chmod(0o644)
            unrelated.chmod(0o644)

            self.assertEqual(secure_existing_photos(image_dir), 1)

            self.assertEqual(stat.S_IMODE(image_dir.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(old_photo.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(unrelated.stat().st_mode), 0o644)


class PhotoTenantNamespaceTests(unittest.TestCase):
    def test_new_upload_filename_carries_the_authenticated_tenant_id(self):
        with tempfile.TemporaryDirectory() as root:
            image_dir = Path(root) / "photos"
            pet = store_pet_photo(
                SimpleNamespace(stream=io.BytesIO(png_bytes())),
                image_dir,
                1024 * 1024,
                tenant_id=42,
            )
            self.assertRegex(pet.filename, r"^t42-[a-f0-9]{32}\.jpg$")
            self.assertTrue((image_dir / pet.filename).is_file())


if __name__ == "__main__":
    unittest.main()

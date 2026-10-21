import contextlib
import io
import unittest
from unittest.mock import patch

from petcare.vision import migrate_media


class _MemoryStorage:
    def __init__(self, initial=None, corrupt_after_write=False):
        self.objects = dict(initial or {})
        self.corrupt_after_write = corrupt_after_write

    def read(self, filename):
        return self.objects[filename]

    def put(self, filename, contents):
        self.objects[filename] = contents + b"corrupt" if self.corrupt_after_write else contents


class MediaMigrationTests(unittest.TestCase):
    def test_copy_verifies_hash_and_keeps_source_objects(self):
        filename = "e" * 32 + ".jpg"
        records = [("pets", filename), ("products", filename)]
        source = {
            ("local", "pets"): _MemoryStorage({filename: b"pet-photo"}),
            ("local", "products"): _MemoryStorage({filename: b"product-photo"}),
        }
        destination = {
            ("s3", "pets"): _MemoryStorage(),
            ("s3", "products"): _MemoryStorage(),
        }
        stores = {**source, **destination}
        with (
            patch.object(migrate_media, "list_referenced_media", return_value=records),
            patch.object(
                migrate_media, "get_media_storage",
                side_effect=lambda _config, category, backend: stores[(backend, category)],
            ),
        ):
            copied = migrate_media.copy_referenced_media("local", "s3")

        self.assertEqual(copied, 2)
        self.assertEqual(source[("local", "pets")].objects[filename], b"pet-photo")
        self.assertEqual(destination[("s3", "pets")].objects[filename], b"pet-photo")
        self.assertEqual(destination[("s3", "products")].objects[filename], b"product-photo")

    def test_copy_fails_verification_without_deleting_source(self):
        filename = "f" * 32 + ".jpg"
        source = _MemoryStorage({filename: b"photo"})
        destination = _MemoryStorage(corrupt_after_write=True)
        with (
            patch.object(migrate_media, "list_referenced_media", return_value=[("pets", filename)]),
            patch.object(
                migrate_media, "get_media_storage",
                side_effect=lambda _config, _category, backend: source if backend == "local" else destination,
            ),
        ):
            with self.assertRaisesRegex(IOError, "verification failed"):
                migrate_media.copy_referenced_media("local", "s3")

        self.assertEqual(source.objects[filename], b"photo")

    def test_same_backend_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must differ"):
            migrate_media.copy_referenced_media("s3", "s3", records=[])

    def test_cli_defaults_to_read_only_dry_run(self):
        with (
            patch.object(migrate_media, "list_referenced_media", return_value=[("pets", "x")]),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            result = migrate_media.main(["--from", "local", "--to", "s3"])

        self.assertEqual(result, 0)
        self.assertIn("Dry run only", output.getvalue())


if __name__ == "__main__":
    unittest.main()

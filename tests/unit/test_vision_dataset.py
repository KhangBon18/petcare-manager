"""Deterministic validation of synthetic image fixtures; never model-accuracy tests."""

from __future__ import annotations

import io
import json
import unittest
from pathlib import Path

from PIL import Image

from petcare.services.exceptions import ValidationError
from petcare.vision.image_features import normalize_image_bytes, read_upload


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "vision"


class VisionSyntheticDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text())

    def test_labeled_supported_illustrations_decode_and_normalize_without_metadata(self):
        for sample in self.manifest["valid_images"]:
            with self.subTest(file=sample["file"]):
                raw = (FIXTURE_DIR / sample["file"]).read_bytes()
                self.assertEqual(read_upload(io.BytesIO(raw), 5 * 1024 * 1024), raw)
                normalized = normalize_image_bytes(raw)
                with Image.open(io.BytesIO(normalized)) as image:
                    self.assertEqual(image.format, "JPEG")
                    self.assertEqual(image.getexif(), {})

    def test_extension_mismatch_is_handled_by_content_not_used_as_a_path(self):
        sample = (FIXTURE_DIR / "extension-mismatch.jpg").read_bytes()

        normalized = normalize_image_bytes(sample)

        with Image.open(io.BytesIO(normalized)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.size, (160, 128))

    def test_unsupported_corrupt_empty_and_oversized_fixtures_are_rejected(self):
        unsupported = (FIXTURE_DIR / "unsupported.gif").read_bytes()
        corrupted = (FIXTURE_DIR / "corrupted.png").read_bytes()
        oversized = (FIXTURE_DIR / "oversized.png").read_bytes()
        empty = (FIXTURE_DIR / "empty.bin").read_bytes()

        for name, contents in (
            ("unsupported", unsupported),
            ("corrupted", corrupted),
            ("oversized", oversized),
        ):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                normalize_image_bytes(contents)
        with self.assertRaises(ValidationError):
            read_upload(io.BytesIO(empty), 5 * 1024 * 1024)

    def test_dataset_documents_integration_scenarios_and_accuracy_limit(self):
        self.assertIn("do not measure", self.manifest["limitations"])
        self.assertIn("concurrent image processing slot", self.manifest["integration_scenarios"])
        self.assertIn("retry after provider failure", self.manifest["integration_scenarios"])


if __name__ == "__main__":
    unittest.main()

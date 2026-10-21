import io
import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from PIL import Image

from petcare.services.exceptions import ValidationError
from petcare.vision.image_features import (
    compare_images,
    compare_images_from_json,
    describe_image,
    descriptor_from_json,
    descriptor_to_json,
    normalize_image_bytes,
    read_upload,
    visual_hash_bands,
)


def png_bytes(color, size=(64, 64)):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return output.getvalue()


def pet_photo_bytes(background, subject=(180, 70, 30)):
    image = Image.new("RGB", (96, 96), background)
    image.paste(Image.new("RGB", (48, 48), subject), (24, 24))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class VisionSearchTests(unittest.TestCase):
    def test_descriptor_round_trips_and_identical_image_matches(self):
        encoded = normalize_image_bytes(png_bytes((218, 178, 82)))
        descriptor = describe_image(encoded)
        restored = descriptor_from_json(descriptor_to_json(descriptor))

        self.assertIsNotNone(restored)
        self.assertIn("vàng", descriptor.dominant_colors)
        self.assertEqual(compare_images(descriptor, restored), 1.0)
        self.assertEqual(descriptor.visual_hash, restored.visual_hash)
        self.assertEqual(len(descriptor.visual_hash), 16)

    def test_visual_hash_bands_are_stable_and_legacy_payload_has_no_index_key(self):
        descriptor = describe_image(normalize_image_bytes(png_bytes((218, 178, 82))))
        legacy = json.loads(descriptor_to_json(descriptor))
        legacy.pop("visual_hash")
        decoded = descriptor_from_json(legacy)

        self.assertEqual(decoded.visual_hash, "")
        self.assertEqual(len(descriptor.visual_hash), 16)
        bands = visual_hash_bands(descriptor.visual_hash)
        self.assertEqual(len(bands), 8)
        self.assertTrue(all(0 <= bucket < 256 for bucket in bands))
        self.assertEqual(
            describe_image(normalize_image_bytes(png_bytes((218, 178, 82)))).visual_hash,
            descriptor.visual_hash,
        )

    def test_different_color_photo_ranks_lower(self):
        yellow = describe_image(normalize_image_bytes(png_bytes((220, 180, 80))))
        blue = describe_image(normalize_image_bytes(png_bytes((30, 80, 210))))

        self.assertLess(compare_images(yellow, blue), compare_images(yellow, yellow))

    def test_center_color_feature_reduces_background_sensitivity(self):
        first = describe_image(normalize_image_bytes(pet_photo_bytes((35, 115, 65))))
        second = describe_image(normalize_image_bytes(pet_photo_bytes((45, 85, 185))))
        legacy_first = replace(first, center_color_histogram=())
        legacy_second = replace(second, center_color_histogram=())

        self.assertGreater(compare_images(first, second), compare_images(legacy_first, legacy_second))
        self.assertEqual(first.dominant_colors[0], "cam")

    def test_old_descriptor_without_center_feature_remains_readable(self):
        encoded = normalize_image_bytes(png_bytes((218, 178, 82)))
        descriptor = describe_image(encoded)
        old_payload = descriptor_to_json(descriptor)
        data = json.loads(old_payload)
        data.pop("center_color_histogram")
        legacy = descriptor_from_json(data)

        self.assertEqual(legacy.center_color_histogram, ())
        self.assertEqual(compare_images(descriptor, legacy), compare_images(
            replace(descriptor, center_color_histogram=()), legacy
        ))

    def test_direct_json_comparison_matches_compatibility_decoder(self):
        first = describe_image(normalize_image_bytes(pet_photo_bytes((35, 115, 65))))
        second = describe_image(normalize_image_bytes(pet_photo_bytes((45, 85, 185))))
        payload = descriptor_to_json(second)

        self.assertEqual(
            compare_images_from_json(first, payload),
            compare_images(first, descriptor_from_json(payload)),
        )

    def test_direct_json_comparison_supports_legacy_and_numeric_string_values(self):
        descriptor = describe_image(normalize_image_bytes(png_bytes((218, 178, 82))))
        data = json.loads(descriptor_to_json(descriptor))
        data.pop("center_color_histogram")
        data["color_histogram"] = [str(item) for item in data["color_histogram"]]
        data["grayscale_grid"] = [str(item) for item in data["grayscale_grid"]]

        self.assertEqual(
            compare_images_from_json(descriptor, data),
            compare_images(descriptor, descriptor_from_json(data)),
        )
        self.assertIsNone(compare_images_from_json(descriptor, {"invalid": True}))

    def test_rejects_unsupported_or_empty_image(self):
        for data in (b"", b"not an image"):
            with self.subTest(data=data):
                with self.assertRaises(ValidationError):
                    describe_image(data)

    def test_upload_byte_limit_is_enforced(self):
        with self.assertRaises(ValidationError):
            read_upload(io.BytesIO(b"12345"), max_bytes=4)

    def test_normalization_avoids_full_size_rgb_copy_before_thumbnail(self):
        source_size = (2400, 1800)
        image_bytes = png_bytes((218, 178, 82), size=source_size)
        original_convert = Image.Image.convert
        converted_sizes = []

        def record_convert(image, *args, **kwargs):
            converted_sizes.append(image.size)
            return original_convert(image, *args, **kwargs)

        with patch.object(Image.Image, "convert", record_convert):
            normalized = normalize_image_bytes(image_bytes)

        self.assertNotIn(source_size, converted_sizes)
        with Image.open(io.BytesIO(normalized)) as result:
            self.assertEqual(result.size, (1600, 1200))

    def test_palette_images_convert_before_thumbnail_for_high_quality_resampling(self):
        source_size = (2400, 1800)
        source = Image.frombytes(
            "P", source_size, bytes((0, 1)) * (source_size[0] * source_size[1] // 2)
        )
        source.putpalette([0, 0, 0, 255, 255, 255] + [0, 0, 0] * 254)
        image_file = io.BytesIO()
        source.save(image_file, format="PNG")
        original_convert = Image.Image.convert
        converted_sizes = []

        def record_convert(image, *args, **kwargs):
            converted_sizes.append(image.size)
            return original_convert(image, *args, **kwargs)

        with patch.object(Image.Image, "convert", record_convert):
            normalized = normalize_image_bytes(image_file.getvalue())

        self.assertIn(source_size, converted_sizes)
        with Image.open(io.BytesIO(normalized)) as result:
            self.assertEqual(result.size, (1600, 1200))
            pixel = result.convert("RGB").getpixel((800, 600))
            self.assertTrue(all(100 <= channel <= 156 for channel in pixel))


if __name__ == "__main__":
    unittest.main()

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber

from petcare.vision.media_storage import (
    LocalMediaStorage,
    S3MediaStorage,
    get_media_storage,
    media_tenant_id,
    validate_media_config,
)


class MediaStorageTests(unittest.TestCase):
    def test_local_storage_writes_reads_and_removes_private_photo(self):
        filename = "a" * 32 + ".jpg"
        with tempfile.TemporaryDirectory() as root:
            storage = LocalMediaStorage(Path(root) / "pets")
            storage.put(filename, b"jpeg-bytes")
            self.assertEqual(storage.read(filename), b"jpeg-bytes")
            storage.delete(filename)
            with self.assertRaises(FileNotFoundError):
                storage.read(filename)

    def test_local_storage_rejects_unsafe_names(self):
        with tempfile.TemporaryDirectory() as root:
            storage = LocalMediaStorage(root)
            with self.assertRaises(ValueError):
                storage.read("../../private.jpg")

    def test_media_names_support_legacy_and_tenant_scoped_identifiers(self):
        self.assertIsNone(media_tenant_id("a" * 32 + ".jpg"))
        self.assertEqual(media_tenant_id("t42-" + "a" * 32 + ".jpg"), 42)
        with self.assertRaises(ValueError):
            media_tenant_id("t0-" + "a" * 32 + ".jpg")

    def test_new_s3_object_key_is_namespaced_by_tenant(self):
        filename = "t42-" + "a" * 32 + ".jpg"
        storage = S3MediaStorage(
            {
                "MEDIA_S3_BUCKET": "petcare-private",
                "MEDIA_S3_PREFIX": "petcare",
            },
            "pets",
        )
        self.assertEqual(
            storage._key(filename),
            f"petcare/tenants/42/pets/{filename}",
        )

    def test_s3_upload_read_and_delete_keep_objects_private(self):
        filename = "b" * 32 + ".jpg"
        contents = b"normalized-jpeg"
        fake_client = boto3.client(
            "s3", region_name="us-east-1", aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
        )
        storage = S3MediaStorage(
            {
                "MEDIA_S3_BUCKET": "petcare-private",
                "MEDIA_S3_REGION": "us-east-1",
                "MEDIA_S3_PREFIX": "petcare",
                "MEDIA_S3_ADDRESSING_STYLE": "path",
                "MEDIA_S3_SERVER_SIDE_ENCRYPTION": "AES256",
                "MEDIA_S3_ACCESS_KEY_ID": "test-key",
                "MEDIA_S3_SECRET_ACCESS_KEY": "test-secret",
            },
            "pets",
        )
        expected_key = f"petcare/pets/{filename}"
        stubber = Stubber(fake_client)
        stubber.add_response(
            "put_object",
            {},
            {
                "Bucket": "petcare-private", "Key": expected_key, "Body": contents,
                "ContentLength": len(contents), "ContentType": "image/jpeg",
                "CacheControl": "private, no-store", "ServerSideEncryption": "AES256",
            },
        )
        stubber.add_response(
            "get_object",
            {
                "Body": StreamingBody(io.BytesIO(contents), len(contents)),
                "ContentLength": len(contents), "ETag": '"test-etag"', "Metadata": {},
            },
            {"Bucket": "petcare-private", "Key": expected_key},
        )
        stubber.add_response(
            "delete_object", {}, {"Bucket": "petcare-private", "Key": expected_key}
        )
        with patch("petcare.vision.media_storage._s3_client", return_value=fake_client):
            with stubber:
                storage.put(filename, contents)
                self.assertEqual(storage.read(filename), contents)
                storage.delete(filename)

    def test_s3_missing_object_maps_to_not_found(self):
        filename = "c" * 32 + ".jpg"
        fake_client = boto3.client(
            "s3", region_name="us-east-1", aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
        )
        stubber = Stubber(fake_client)
        stubber.add_client_error(
            "get_object", service_error_code="NoSuchKey", http_status_code=404,
            expected_params={"Bucket": "petcare-private", "Key": f"pets/{filename}"},
        )
        storage = S3MediaStorage(
            {"MEDIA_S3_BUCKET": "petcare-private", "MEDIA_S3_ADDRESSING_STYLE": "path"},
            "pets",
        )
        with patch("petcare.vision.media_storage._s3_client", return_value=fake_client):
            with stubber, self.assertRaises(FileNotFoundError):
                storage.read(filename)

    def test_s3_config_requires_bucket_and_complete_credentials(self):
        with self.assertRaisesRegex(RuntimeError, "MEDIA_S3_BUCKET"):
            validate_media_config({"MEDIA_STORAGE_BACKEND": "s3"})
        with self.assertRaisesRegex(RuntimeError, "set together"):
            validate_media_config({
                "MEDIA_STORAGE_BACKEND": "s3", "MEDIA_S3_BUCKET": "private",
                "MEDIA_S3_ACCESS_KEY_ID": "only-half-a-credential",
            })

    def test_production_rejects_http_object_storage_endpoint(self):
        with self.assertRaisesRegex(RuntimeError, "HTTPS"):
            validate_media_config({
                "MEDIA_STORAGE_BACKEND": "s3", "MEDIA_S3_BUCKET": "private",
                "MEDIA_S3_ENDPOINT_URL": "http://storage.example.test",
                "APP_ENV": "production",
            })

    def test_backend_factory_uses_local_by_default(self):
        with tempfile.TemporaryDirectory() as root:
            storage = get_media_storage({"PET_IMAGE_DIR": root}, "pets")
            self.assertIsInstance(storage, LocalMediaStorage)


if __name__ == "__main__":
    unittest.main()

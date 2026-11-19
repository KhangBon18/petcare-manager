"""Private local or S3-compatible storage for encrypted tenant export artifacts."""

from contextlib import contextmanager
import os
from pathlib import Path
import re
import tempfile

from botocore.exceptions import ClientError

from petcare.vision.media_storage import _s3_client, validate_media_config

_SAFE_KEY = re.compile(r"^tenants/([1-9][0-9]{0,19})/exports/([a-f0-9]{32})\.pcarexport$")


def validate_export_storage_config(config):
    backend = str(config.get("TENANT_EXPORT_STORAGE_BACKEND", "local")).strip().lower()
    if backend not in {"local", "s3"}:
        raise RuntimeError("TENANT_EXPORT_STORAGE_BACKEND must be 'local' or 's3'.")
    if backend == "s3":
        media_config = dict(config)
        media_config["MEDIA_STORAGE_BACKEND"] = "s3"
        validate_media_config(media_config)
    elif not str(config.get("TENANT_EXPORT_DIR", "")).strip():
        raise RuntimeError("TENANT_EXPORT_DIR is required for local tenant export storage.")


def _safe_key(key):
    if not isinstance(key, str) or not _SAFE_KEY.fullmatch(key):
        raise ValueError("Unsafe tenant export storage key.")
    return key


def _ensure_private_directory(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        directory.chmod(0o700)
    return directory.resolve()


class LocalExportStorage:
    def __init__(self, directory):
        self.directory = Path(directory)

    def _path(self, key, create_parent=False):
        key = _safe_key(key)
        root = _ensure_private_directory(self.directory)
        path = root.joinpath(*key.split("/"))
        if create_parent:
            parent = _ensure_private_directory(path.parent)
            parent_is_private = parent.is_relative_to(root)
        else:
            parent_is_private = path.resolve().is_relative_to(root)
        if not parent_is_private or path.is_symlink():
            raise ValueError("Unsafe tenant export storage path.")
        return path

    def put(self, key, source_path):
        path = self._path(key, create_parent=True)
        temp_path = None
        try:
            descriptor, temp_path = tempfile.mkstemp(prefix=".export-", dir=path.parent)
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as target, Path(source_path).open("rb") as source:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            # A hard link publishes atomically without replacing an existing key.
            os.link(temp_path, path)
            return path.stat().st_size
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    @contextmanager
    def open(self, key):
        path = self._path(key)
        root = _ensure_private_directory(self.directory)
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            raise FileNotFoundError(key)
        with path.open("rb") as source:
            yield source

    def delete(self, key):
        path = self._path(key)
        if path.is_symlink():
            raise OSError("Refusing to delete a tenant export symlink.")
        path.unlink(missing_ok=True)

    def exists(self, key):
        path = self._path(key)
        return path.is_file() and not path.is_symlink()


class S3ExportStorage:
    def __init__(self, config):
        self.bucket = str(config.get("MEDIA_S3_BUCKET", "")).strip()
        self.region = str(config.get("MEDIA_S3_REGION", "")).strip()
        self.endpoint = str(config.get("MEDIA_S3_ENDPOINT_URL", "")).strip()
        self.access_key = str(config.get("MEDIA_S3_ACCESS_KEY_ID", "")).strip()
        self.secret_key = str(config.get("MEDIA_S3_SECRET_ACCESS_KEY", ""))
        self.addressing_style = str(config.get("MEDIA_S3_ADDRESSING_STYLE", "auto")).strip().lower()
        self.prefix = str(config.get("MEDIA_S3_PREFIX", "")).strip("/")
        self.encryption = str(config.get("MEDIA_S3_SERVER_SIDE_ENCRYPTION", "AES256")).strip()

    @property
    def client(self):
        return _s3_client(
            self.region, self.endpoint, self.access_key, self.secret_key, self.addressing_style
        )

    def _key(self, key):
        key = _safe_key(key)
        return "/".join(part for part in (self.prefix, key) if part)

    def put(self, key, source_path):
        from boto3.s3.transfer import TransferConfig

        source_path = Path(source_path)
        extra_args = {
            "ContentType": "application/vnd.petcare.encrypted-export",
            "CacheControl": "private, no-store",
        }
        if self.encryption:
            extra_args["ServerSideEncryption"] = self.encryption
        self.client.upload_file(
            str(source_path),
            self.bucket,
            self._key(key),
            ExtraArgs=extra_args,
            Config=TransferConfig(
                multipart_threshold=16 * 1024 * 1024,
                multipart_chunksize=8 * 1024 * 1024,
                max_concurrency=4,
                use_threads=True,
            ),
        )
        return source_path.stat().st_size

    @contextmanager
    def open(self, key):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(key) from exc
            raise
        body = response["Body"]
        try:
            yield body
        finally:
            body.close()

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))

    def exists(self, key):
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(key))
            return True
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise


def get_export_storage(config):
    validate_export_storage_config(config)
    if str(config.get("TENANT_EXPORT_STORAGE_BACKEND", "local")).strip().lower() == "s3":
        return S3ExportStorage(config)
    return LocalExportStorage(config["TENANT_EXPORT_DIR"])

"""Private local and S3-compatible storage for normalized pet/shop images."""

from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError


SAFE_MEDIA_NAME = re.compile(r"^(?:t([1-9][0-9]{0,19})-)?([a-f0-9]{32})\.jpg$")
MAX_STORED_MEDIA_BYTES = 10 * 1024 * 1024


class MediaStorageError(RuntimeError):
    """Raised when private media cannot be read or written safely."""


def _setting(config, name, default=None):
    if hasattr(config, "get"):
        return config.get(name, default)
    return getattr(config, name, default)


def validate_media_config(config):
    backend = str(_setting(config, "MEDIA_STORAGE_BACKEND", "local")).strip().lower()
    if backend not in {"local", "s3"}:
        raise RuntimeError("MEDIA_STORAGE_BACKEND must be 'local' or 's3'.")
    if backend == "local":
        return

    bucket = str(_setting(config, "MEDIA_S3_BUCKET", "")).strip()
    if not bucket:
        raise RuntimeError("MEDIA_S3_BUCKET is required when S3 media storage is enabled.")
    access_key = str(_setting(config, "MEDIA_S3_ACCESS_KEY_ID", "")).strip()
    secret_key = str(_setting(config, "MEDIA_S3_SECRET_ACCESS_KEY", ""))
    if bool(access_key) != bool(secret_key):
        raise RuntimeError("S3 access key ID and secret access key must be set together.")
    style = str(_setting(config, "MEDIA_S3_ADDRESSING_STYLE", "auto")).strip().lower()
    if style not in {"auto", "path", "virtual"}:
        raise RuntimeError("MEDIA_S3_ADDRESSING_STYLE must be auto, path or virtual.")

    endpoint = str(_setting(config, "MEDIA_S3_ENDPOINT_URL", "")).strip()
    if endpoint:
        parsed = urlsplit(endpoint)
        try:
            parsed.port
        except ValueError as exc:
            raise RuntimeError("MEDIA_S3_ENDPOINT_URL has an invalid port.") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError("MEDIA_S3_ENDPOINT_URL must be a valid HTTP(S) origin without credentials.")
        if _setting(config, "APP_ENV", "development") == "production" and parsed.scheme != "https":
            raise RuntimeError("Production requires HTTPS for a custom S3 endpoint.")

    prefix = str(_setting(config, "MEDIA_S3_PREFIX", "")).strip("/")
    if "\\" in prefix or any(part in {".", ".."} for part in prefix.split("/")):
        raise RuntimeError("MEDIA_S3_PREFIX contains an unsafe path segment.")
    encryption = str(_setting(config, "MEDIA_S3_SERVER_SIDE_ENCRYPTION", "AES256")).strip()
    if encryption not in {"", "AES256"}:
        raise RuntimeError("MEDIA_S3_SERVER_SIDE_ENCRYPTION must be blank or AES256.")


def _safe_name(filename):
    if not isinstance(filename, str) or not SAFE_MEDIA_NAME.fullmatch(filename):
        raise ValueError("Unsafe photo filename.")
    return filename


def media_tenant_id(filename: str) -> int | None:
    """Return the tenant namespace embedded in new media names, if present.

    Old UUID-only names remain readable for compatibility with existing rows.
    New uploads encode the owning tenant so shared object storage cannot
    overwrite a different store's object even if a filename is reused.
    """
    match = SAFE_MEDIA_NAME.fullmatch(filename) if isinstance(filename, str) else None
    if not match:
        raise ValueError("Unsafe photo filename.")
    return int(match.group(1)) if match.group(1) else None


def _ensure_private_directory(directory: str | Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        directory.chmod(0o700)
    return directory


class LocalMediaStorage:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def put(self, filename: str, contents: bytes) -> None:
        filename = _safe_name(filename)
        directory = _ensure_private_directory(self.directory)
        target = directory / filename
        temporary = directory / f".{filename}.tmp"
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as output:
                output.write(contents)
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    @contextmanager
    def open(self, filename: str):
        filename = _safe_name(filename)
        directory = self.directory.resolve()
        path = directory / filename
        if path.is_symlink() or not path.resolve().is_relative_to(directory) or not path.is_file():
            raise FileNotFoundError(filename)
        with path.open("rb") as source:
            yield source

    def read(self, filename: str) -> bytes:
        with self.open(filename) as source:
            contents = source.read(MAX_STORED_MEDIA_BYTES + 1)
        if len(contents) > MAX_STORED_MEDIA_BYTES:
            raise MediaStorageError("Stored image exceeds the configured safety limit.")
        return contents

    def delete(self, filename: str | None) -> None:
        if not filename:
            return
        filename = _safe_name(filename)
        path = self.directory / filename
        if path.is_symlink():
            raise MediaStorageError("Refusing to delete a photo symlink.")
        try:
            path.unlink()
        except FileNotFoundError:
            pass


@lru_cache(maxsize=16)
def _s3_client(region: str, endpoint: str, access_key: str, secret_key: str, addressing_style: str):
    import boto3

    kwargs = {
        "region_name": region or None,
        "endpoint_url": endpoint or None,
        "config": BotoConfig(
            s3={"addressing_style": addressing_style},
            connect_timeout=3,
            read_timeout=15,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    }
    if access_key:
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret_key
    return boto3.client("s3", **kwargs)


class S3MediaStorage:
    def __init__(self, config, category: str):
        self.bucket = str(_setting(config, "MEDIA_S3_BUCKET", "")).strip()
        self.region = str(_setting(config, "MEDIA_S3_REGION", "")).strip()
        self.endpoint = str(_setting(config, "MEDIA_S3_ENDPOINT_URL", "")).strip()
        self.access_key = str(_setting(config, "MEDIA_S3_ACCESS_KEY_ID", "")).strip()
        self.secret_key = str(_setting(config, "MEDIA_S3_SECRET_ACCESS_KEY", ""))
        self.addressing_style = str(_setting(config, "MEDIA_S3_ADDRESSING_STYLE", "auto")).strip().lower()
        self.prefix = str(_setting(config, "MEDIA_S3_PREFIX", "")).strip("/")
        self.encryption = str(_setting(config, "MEDIA_S3_SERVER_SIDE_ENCRYPTION", "AES256")).strip()
        if category not in {"pets", "products"}:
            raise ValueError("Unknown media category.")
        self.category = category

    @property
    def client(self):
        return _s3_client(
            self.region, self.endpoint, self.access_key, self.secret_key, self.addressing_style
        )

    def _key(self, filename):
        filename = _safe_name(filename)
        tenant_id = media_tenant_id(filename)
        namespace = f"tenants/{tenant_id}" if tenant_id is not None else ""
        parts = [part for part in (self.prefix, namespace, self.category, filename) if part]
        return "/".join(parts)

    def put(self, filename: str, contents: bytes) -> None:
        filename = _safe_name(filename)
        if len(contents) > MAX_STORED_MEDIA_BYTES:
            raise MediaStorageError("Stored image exceeds the configured safety limit.")
        request = {
            "Bucket": self.bucket,
            "Key": self._key(filename),
            "Body": contents,
            "ContentLength": len(contents),
            "ContentType": "image/jpeg",
            "CacheControl": "private, no-store",
        }
        if self.encryption:
            request["ServerSideEncryption"] = self.encryption
        try:
            self.client.put_object(**request)
        except Exception as exc:
            raise MediaStorageError("Could not store the image in object storage.") from exc

    @contextmanager
    def open(self, filename: str):
        key = self._key(filename)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(filename) from exc
            raise MediaStorageError("Could not read the image from object storage.") from exc
        except Exception as exc:
            raise MediaStorageError("Could not read the image from object storage.") from exc
        body = response["Body"]
        try:
            if int(response.get("ContentLength", 0)) > MAX_STORED_MEDIA_BYTES:
                raise MediaStorageError("Stored image exceeds the configured safety limit.")
            yield body
        finally:
            body.close()

    def read(self, filename: str) -> bytes:
        with self.open(filename) as source:
            contents = source.read(MAX_STORED_MEDIA_BYTES + 1)
        if len(contents) > MAX_STORED_MEDIA_BYTES:
            raise MediaStorageError("Stored image exceeds the configured safety limit.")
        return contents

    def delete(self, filename: str | None) -> None:
        if not filename:
            return
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self._key(filename))
        except Exception as exc:
            raise MediaStorageError("Could not remove the image from object storage.") from exc


def get_media_storage(config, category: str, backend: str | None = None):
    if category not in {"pets", "products"}:
        raise ValueError("Unknown media category.")
    backend = str(backend or _setting(config, "MEDIA_STORAGE_BACKEND", "local")).strip().lower()
    validation_config = config
    if backend != str(_setting(config, "MEDIA_STORAGE_BACKEND", "local")).strip().lower():
        try:
            validation_config = dict(config)
        except (TypeError, ValueError):
            validation_config = vars(config).copy()
        validation_config["MEDIA_STORAGE_BACKEND"] = backend
    validate_media_config(validation_config)
    if backend == "local":
        directory_key = "PET_IMAGE_DIR" if category == "pets" else "PRODUCT_IMAGE_DIR"
        return LocalMediaStorage(_setting(config, directory_key))
    return S3MediaStorage(config, category)

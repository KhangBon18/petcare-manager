"""Streaming authenticated encryption for private operator bundles."""

from __future__ import annotations

import io
import os
import secrets
import struct
import tempfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


ENCRYPTED_FILE_HEADER = struct.Struct(">8sI16s12s")
ENCRYPTED_FILE_TAG_BYTES = 16
KDF_ITERATIONS = 600_000
MIN_KDF_ITERATIONS = 600_000
MAX_KDF_ITERATIONS = 2_000_000
MAX_GCM_PLAINTEXT_BYTES = (1 << 36) - 32
MIN_PASSPHRASE_LENGTH = 12
MAX_PASSPHRASE_BYTES = 1024


def validate_passphrase(passphrase: str) -> bytes:
    if not isinstance(passphrase, str) or len(passphrase) < MIN_PASSPHRASE_LENGTH:
        raise ValueError("Passphrase must be at least 12 characters long.")
    encoded = passphrase.encode("utf-8")
    if len(encoded) > MAX_PASSPHRASE_BYTES:
        raise ValueError("Passphrase is too long.")
    return encoded


def _derive_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(validate_passphrase(passphrase))


class AuthenticatedEncryptingWriter:
    """Non-seekable writer that authenticates a fixed format magic and streams AES-GCM."""

    def __init__(self, output_stream, passphrase: str, magic: bytes):
        if not isinstance(magic, bytes) or len(magic) != 8:
            raise ValueError("Encrypted bundle magic must be exactly 8 bytes.")
        self._output = output_stream
        self._position = 0
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(12)
        self._header = ENCRYPTED_FILE_HEADER.pack(magic, KDF_ITERATIONS, salt, nonce)
        self._encryptor = Cipher(
            algorithms.AES(_derive_key(passphrase, salt, KDF_ITERATIONS)),
            modes.GCM(nonce),
        ).encryptor()
        self._encryptor.authenticate_additional_data(self._header)
        self._output.write(self._header)

    def write(self, value: bytes) -> int:
        if self._position + len(value) > MAX_GCM_PLAINTEXT_BYTES:
            raise ValueError("Encrypted bundle exceeds the supported AES-GCM size limit.")
        encrypted = self._encryptor.update(value)
        if encrypted:
            self._output.write(encrypted)
        self._position += len(value)
        return len(value)

    def tell(self) -> int:
        return self._position

    def seek(self, *_args):
        raise io.UnsupportedOperation("Encrypted bundle stream is not seekable.")

    def flush(self) -> None:
        self._output.flush()

    def finish(self) -> None:
        self._output.write(self._encryptor.finalize())
        self._output.write(self._encryptor.tag)
        self._output.flush()
        if hasattr(self._output, "fileno"):
            os.fsync(self._output.fileno())


def decrypt_to_private_temp(
    encrypted_path: Path | str,
    passphrase: str,
    expected_magic: bytes,
    *,
    suffix: str = ".data",
) -> Path:
    """Authenticate a bundle to a mode-0600 temp file; return only after tag verification."""
    temp_descriptor, temp_name = tempfile.mkstemp(prefix=".petcare-decrypt-", suffix=suffix)
    temp_path = Path(temp_name)
    try:
        with Path(encrypted_path).open("rb") as source:
            header = source.read(ENCRYPTED_FILE_HEADER.size)
            if len(header) != ENCRYPTED_FILE_HEADER.size:
                raise ValueError("Encrypted bundle header is missing or incomplete.")
            magic, iterations, salt, nonce = ENCRYPTED_FILE_HEADER.unpack(header)
            if magic != expected_magic:
                raise ValueError("Unsupported or unencrypted bundle format.")
            if not MIN_KDF_ITERATIONS <= iterations <= MAX_KDF_ITERATIONS:
                raise ValueError("Bundle key-derivation settings are outside the supported range.")
            source.seek(0, os.SEEK_END)
            encrypted_size = source.tell()
            ciphertext_size = encrypted_size - ENCRYPTED_FILE_HEADER.size - ENCRYPTED_FILE_TAG_BYTES
            if ciphertext_size <= 0 or ciphertext_size > MAX_GCM_PLAINTEXT_BYTES:
                raise ValueError("Encrypted bundle is empty, truncated, or too large.")
            source.seek(encrypted_size - ENCRYPTED_FILE_TAG_BYTES)
            tag = source.read(ENCRYPTED_FILE_TAG_BYTES)
            if len(tag) != ENCRYPTED_FILE_TAG_BYTES:
                raise ValueError("Encrypted bundle authentication tag is incomplete.")
            source.seek(ENCRYPTED_FILE_HEADER.size)
            decryptor = Cipher(
                algorithms.AES(_derive_key(passphrase, salt, iterations)),
                modes.GCM(nonce, tag),
            ).decryptor()
            decryptor.authenticate_additional_data(header)
            remaining = ciphertext_size
            plaintext_stream = os.fdopen(temp_descriptor, "wb")
            temp_descriptor = None
            with plaintext_stream as plaintext:
                while remaining:
                    block = source.read(min(1024 * 1024, remaining))
                    if not block:
                        raise ValueError("Encrypted bundle is truncated.")
                    remaining -= len(block)
                    plaintext.write(decryptor.update(block))
                # GCM plaintext is untrusted until finalize authenticates the tag.
                plaintext.write(decryptor.finalize())
                plaintext.flush()
                os.fsync(plaintext.fileno())
        return temp_path
    except InvalidTag as exc:
        temp_path.unlink(missing_ok=True)
        raise ValueError("Passphrase is incorrect or encrypted bundle was modified.") from exc
    except Exception:
        if temp_descriptor is not None:
            os.close(temp_descriptor)
        temp_path.unlink(missing_ok=True)
        raise

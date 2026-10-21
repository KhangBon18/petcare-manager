#!/usr/bin/env python3
"""Create and verify private MySQL + photo backups for the Compose deployment."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import BinaryIO

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from petcare.config import Config  # noqa: E402
from petcare.secure_bundle import (  # noqa: E402
    AuthenticatedEncryptingWriter,
    decrypt_to_private_temp,
    validate_passphrase,
)

FORMAT_VERSION = 1
BACKUP_MAGIC = b"PCBKP001"
PAYLOADS = ("database.sql", "media.tar.gz")
READ_CHUNK = 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
MAX_MEDIA_MEMBERS = 100_000

MYSQLDUMP_SCRIPT = r"""
set -eu
umask 077
option_file="$(mktemp)"
trap 'rm -f "$option_file"' EXIT HUP INT TERM
cat > "$option_file"
mysqldump --defaults-extra-file="$option_file" --single-transaction --quick \
  --no-tablespaces --set-gtid-purged=OFF --default-character-set=utf8mb4 "$1"
""".strip()

COMPOSE_MEDIA_SCRIPT = (
    "import sys; from pathlib import Path; "
    "sys.path.insert(0, '/app/scripts'); "
    "from petcare_backup import create_media_archive; "
    "create_media_archive(Path('/app/instance/pet-images'), "
    "Path('/app/instance/product-images'), sys.stdout.buffer)"
)


class BackupError(Exception):
    """A safe, user-facing backup failure."""


def _sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(READ_CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _add_file(archive: tarfile.TarFile, path: Path, arcname: str, mode: int = 0o644) -> None:
    info = tarfile.TarInfo(arcname)
    info.size = path.stat().st_size
    info.mtime = int(path.stat().st_mtime)
    info.mode = mode
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    with path.open("rb") as stream:
        archive.addfile(info, stream)


def create_media_archive(pet_image_dir: Path, product_image_dir: Path, output: BinaryIO) -> None:
    """Write an inner gzip tar with only regular image files and safe relative names."""
    roots = ((pet_image_dir, "pet-images"), (product_image_dir, "product-images"))
    with tarfile.open(fileobj=output, mode="w|gz", compresslevel=6) as archive:
        for root, archive_root in roots:
            if root.is_symlink():
                raise BackupError(f"Thư mục ảnh không được là liên kết tượng trưng: {root}")
            root.mkdir(parents=True, exist_ok=True)
            root_info = tarfile.TarInfo(archive_root)
            root_info.type = tarfile.DIRTYPE
            root_info.mode = 0o755
            archive.addfile(root_info)

            for current, directories, filenames in os.walk(root, followlinks=False):
                current_path = Path(current)
                directories.sort()
                filenames.sort()
                for name in list(directories):
                    item = current_path / name
                    if item.is_symlink():
                        raise BackupError(f"Không sao lưu liên kết tượng trưng trong thư mục ảnh: {item}")
                    relative = item.relative_to(root).as_posix()
                    info = tarfile.TarInfo(f"{archive_root}/{relative}")
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755
                    archive.addfile(info)

                for name in filenames:
                    item = current_path / name
                    if item.is_symlink() or not item.is_file():
                        raise BackupError(f"Thư mục ảnh có mục không phải file thường: {item}")
                    relative = item.relative_to(root).as_posix()
                    _add_file(archive, item, f"{archive_root}/{relative}")


def _compose_command(*args: str) -> list[str]:
    docker = shutil.which("docker")
    if not docker:
        raise BackupError("Không tìm thấy Docker CLI. Hãy cài Docker Desktop và khởi động dịch vụ MySQL.")
    return [docker, "compose", "--project-directory", str(ROOT_DIR), *args]


def _mysql_option_file() -> bytes:
    password = os.environ.get("MYSQL_ROOT_PASSWORD")
    if password is None:
        raise BackupError("MYSQL_ROOT_PASSWORD chưa được đặt trong môi trường hoặc file .env.")
    if "\n" in password or "\r" in password:
        raise BackupError("MYSQL_ROOT_PASSWORD không được chứa ký tự xuống dòng.")
    escaped = password.replace("\\", "\\\\").replace('"', '\\"')
    return (
        '[client]\nuser=root\npassword="' + escaped +
        '"\nprotocol=tcp\nhost=127.0.0.1\n'
    ).encode("utf-8")


def _run_to_file(
    command: list[str],
    destination: Path,
    *,
    label: str,
    input_data: bytes | None = None,
) -> None:
    """Stream container output to a private staging file without buffering the dump in RAM."""
    try:
        with destination.open("wb") as stdout_file:
            process = subprocess.run(
                command,
                cwd=ROOT_DIR,
                stdout=stdout_file,
                stderr=subprocess.PIPE,
                input=input_data,
                check=False,
                text=False,
            )
    except OSError as error:
        raise BackupError(f"Không chạy được {label}: {error}") from error
    if process.returncode != 0:
        destination.unlink(missing_ok=True)
        details = process.stderr.decode("utf-8", errors="replace")[-3000:].strip()
        raise BackupError(f"{label} thất bại (exit {process.returncode}). Kiểm tra container đang chạy.\n{details}")
    if destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)
        raise BackupError(f"{label} trả về file rỗng.")


def _database_name(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_]{0,63}", value):
        raise BackupError("Tên database chỉ được gồm chữ, số và dấu gạch dưới (tối đa 64 ký tự).")
    return value


def _safe_tar_name(name: str) -> PurePosixPath:
    if not isinstance(name, str) or "\\" in name or "\x00" in name:
        raise BackupError(f"Đường dẫn không an toàn trong backup: {name!r}")
    raw_parts = name.split("/")
    if (
        name.startswith("/")
        or not raw_parts
        or any(part in {"", ".", ".."} for part in raw_parts)
        or ":" in raw_parts[0]
    ):
        raise BackupError(f"Đường dẫn không an toàn trong backup: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute():
        raise BackupError(f"Đường dẫn không an toàn trong backup: {name!r}")
    return path


def _validate_media_archive(path: Path) -> int:
    count = 0
    seen: set[str] = set()
    files: set[str] = set()
    try:
        with tarfile.open(path, mode="r:gz") as media:
            for member in media:
                count += 1
                if count > MAX_MEDIA_MEMBERS:
                    raise BackupError("Backup có quá nhiều mục ảnh để xác minh.")
                relative = _safe_tar_name(member.name)
                if relative.parts[0] not in {"pet-images", "product-images"}:
                    raise BackupError(f"Có đường dẫn ngoài thư mục ảnh trong backup: {member.name}")
                if member.name in seen:
                    raise BackupError(f"Có đường dẫn ảnh trùng trong backup: {member.name}")
                if len(relative.parts) == 1 and not member.isdir():
                    raise BackupError(f"Thư mục gốc ảnh không hợp lệ: {member.name}")
                for parent in relative.parents:
                    if parent == PurePosixPath("."):
                        continue
                    if parent.as_posix() in files:
                        raise BackupError(f"File ảnh đang được dùng làm thư mục cha: {parent}")
                if member.isfile():
                    prefix = f"{member.name}/"
                    if any(existing.startswith(prefix) for existing in seen):
                        raise BackupError(f"File ảnh có đường dẫn con không hợp lệ: {member.name}")
                    files.add(member.name)
                seen.add(member.name)
                if not (member.isdir() or member.isfile()):
                    raise BackupError(f"Backup ảnh chứa liên kết hoặc loại file không hỗ trợ: {member.name}")
    except (OSError, tarfile.TarError) as error:
        raise BackupError(f"Không đọc được gói ảnh bên trong backup: {error}") from error
    return count


def _manifest_bytes(database: str, created_at: str, payload_info: dict[str, dict[str, object]]) -> bytes:
    manifest = {
        "format_version": FORMAT_VERSION,
        "created_at_utc": created_at,
        "database": database,
        "files": payload_info,
    }
    return (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def create_backup(output_path: Path, database: str, media_source: str, passphrase: str) -> Path:
    try:
        validate_passphrase(passphrase)
    except ValueError as error:
        raise BackupError(str(error)) from error
    database = _database_name(database)
    if media_source not in {"host", "compose"}:
        raise BackupError("Nguồn ảnh không hợp lệ.")
    if getattr(Config, "MEDIA_STORAGE_BACKEND", "local") != "local":
        raise BackupError(
            "Tiện ích backup local chỉ đóng gói được media trên filesystem. "
            "Hãy sao lưu database và bucket object storage bằng backup/versioning do provider quản lý."
        )
    output_path = output_path.expanduser().resolve()
    if output_path.exists():
        raise BackupError(f"Không ghi đè backup đã tồn tại: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if output_path.parent == (ROOT_DIR / "backups").resolve():
        output_path.parent.chmod(0o700)

    output_created = False
    try:
        with tempfile.TemporaryDirectory(prefix="petcare-backup-", dir=output_path.parent) as temp_name:
            staging = Path(temp_name)
            sql_path = staging / "database.sql"
            media_path = staging / "media.tar.gz"
            _run_to_file(
                _compose_command("exec", "-T", "mysql", "sh", "-eu", "-c", MYSQLDUMP_SCRIPT,
                                 "petcare-backup", database),
                sql_path,
                label="MySQL dump",
                input_data=_mysql_option_file(),
            )

            if media_source == "host":
                with media_path.open("wb") as output:
                    create_media_archive(
                        Path(Config.PET_IMAGE_DIR), Path(Config.PRODUCT_IMAGE_DIR), output
                    )
            elif media_source == "compose":
                _run_to_file(
                    _compose_command("exec", "-T", "web", "python", "-c", COMPOSE_MEDIA_SCRIPT),
                    media_path,
                    label="Sao lưu ảnh trong volume của web container",
                )
            else:
                raise BackupError("Nguồn ảnh không hợp lệ.")

            payload_info: dict[str, dict[str, object]] = {}
            for name, path in (("database.sql", sql_path), ("media.tar.gz", media_path)):
                digest, size = _sha256(path)
                payload_info[name] = {"sha256": digest, "size_bytes": size}
            created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            manifest_data = _manifest_bytes(database, created_at, payload_info)
            if len(manifest_data) > MAX_MANIFEST_BYTES:
                raise BackupError("Manifest backup vượt giới hạn an toàn.")

            temporary_file = tempfile.NamedTemporaryFile(
                prefix=f".{output_path.name}.", suffix=".partial", dir=output_path.parent, delete=False
            )
            temporary_archive = Path(temporary_file.name)
            temporary_file.close()
            try:
                with temporary_archive.open("wb") as destination:
                    encrypted_stream = AuthenticatedEncryptingWriter(
                        destination, passphrase, BACKUP_MAGIC
                    )
                    with tarfile.open(
                        fileobj=encrypted_stream, mode="w|gz", compresslevel=6
                    ) as archive:
                        _add_file(archive, sql_path, "database.sql", mode=0o600)
                        _add_file(archive, media_path, "media.tar.gz", mode=0o600)
                        info = tarfile.TarInfo("manifest.json")
                        info.size = len(manifest_data)
                        info.mtime = int(datetime.now(timezone.utc).timestamp())
                        info.mode = 0o600
                        archive.addfile(info, io.BytesIO(manifest_data))
                    encrypted_stream.finish()
                    destination.flush()
                    os.fsync(destination.fileno())
                temporary_archive.chmod(0o600)
                try:
                    os.link(temporary_archive, output_path)
                except FileExistsError as error:
                    raise BackupError(f"Không ghi đè backup đã tồn tại: {output_path}") from error
                output_created = True
            finally:
                temporary_archive.unlink(missing_ok=True)

        verify_backup(output_path, passphrase)
        output_created = False
        return output_path
    finally:
        if output_created:
            output_path.unlink(missing_ok=True)


def _verify_plain_backup(path: Path) -> dict[str, object]:
    path = path.expanduser().resolve()
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members = []
            for member in archive:
                members.append(member)
                if len(members) > 3:
                    raise BackupError("Archive chứa nhiều file hơn định dạng hỗ trợ.")
            names = [member.name for member in members]
            if len(names) != 3 or set(names) != {"manifest.json", *PAYLOADS}:
                raise BackupError("Archive phải chứa đúng manifest.json, database.sql và media.tar.gz.")
            if len(names) != len(set(names)):
                raise BackupError("Archive có tên file trùng.")
            by_name = {member.name: member for member in members}
            if any(not by_name[name].isfile() for name in by_name):
                raise BackupError("Archive chỉ được chứa file thường.")
            manifest_member = by_name["manifest.json"]
            if manifest_member.size > MAX_MANIFEST_BYTES:
                raise BackupError("Manifest vượt giới hạn an toàn.")
            manifest_file = archive.extractfile(manifest_member)
            if manifest_file is None:
                raise BackupError("Không đọc được manifest.")
            manifest = json.loads(manifest_file.read(MAX_MANIFEST_BYTES + 1).decode("utf-8"))
            if not isinstance(manifest, dict):
                raise BackupError("Manifest không đúng định dạng.")
            if manifest.get("format_version") != FORMAT_VERSION:
                raise BackupError("Phiên bản định dạng backup không được hỗ trợ.")
            _database_name(manifest.get("database", ""))
            expected_files = manifest.get("files")
            if not isinstance(expected_files, dict) or set(expected_files) != set(PAYLOADS):
                raise BackupError("Manifest không khớp với danh sách file backup.")

            media_temp = tempfile.NamedTemporaryFile(prefix="petcare-verify-media-", suffix=".tar.gz", delete=False)
            media_path = Path(media_temp.name)
            try:
                for name in PAYLOADS:
                    member = by_name[name]
                    source = archive.extractfile(member)
                    if source is None:
                        raise BackupError(f"Không đọc được {name}.")
                    digest = hashlib.sha256()
                    size = 0
                    destination = media_temp if name == "media.tar.gz" else None
                    with source:
                        while chunk := source.read(READ_CHUNK):
                            digest.update(chunk)
                            size += len(chunk)
                            if destination is not None:
                                destination.write(chunk)
                    expected = expected_files[name]
                    if not isinstance(expected, dict):
                        raise BackupError(f"Manifest thiếu metadata cho {name}.")
                    if size != expected.get("size_bytes") or digest.hexdigest() != expected.get("sha256"):
                        raise BackupError(f"Checksum không khớp: {name}.")
                media_temp.flush()
            finally:
                media_temp.close()
            try:
                media_count = _validate_media_archive(media_path)
            finally:
                media_path.unlink(missing_ok=True)
            return {
                "database": manifest["database"],
                "created_at_utc": manifest.get("created_at_utc", ""),
                "media_entries": media_count,
                "size_bytes": path.stat().st_size,
            }
    except BackupError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, tarfile.TarError) as error:
        raise BackupError(f"Không thể xác minh backup: {error}") from error


def verify_backup(path: Path, passphrase: str) -> dict[str, object]:
    try:
        plaintext_path = decrypt_to_private_temp(
            path, passphrase, BACKUP_MAGIC, suffix=".tar.gz"
        )
    except ValueError as error:
        raise BackupError(str(error)) from error
    try:
        return _verify_plain_backup(plaintext_path)
    finally:
        plaintext_path.unlink(missing_ok=True)


def encrypt_legacy_backup(archive_path: Path, output_path: Path, passphrase: str) -> Path:
    """Verify and encrypt a pre-encryption tar.gz without modifying the source archive."""
    try:
        validate_passphrase(passphrase)
    except ValueError as error:
        raise BackupError(str(error)) from error
    _verify_plain_backup(archive_path)
    output_path = output_path.expanduser().resolve()
    if output_path.exists():
        raise BackupError(f"Không ghi đè backup đã tồn tại: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    temporary_file = tempfile.NamedTemporaryFile(
        prefix=f".{output_path.name}.", suffix=".partial", dir=output_path.parent, delete=False
    )
    temporary_archive = Path(temporary_file.name)
    temporary_file.close()
    output_created = False
    try:
        with temporary_archive.open("wb") as destination:
            encrypted_stream = AuthenticatedEncryptingWriter(
                destination, passphrase, BACKUP_MAGIC
            )
            with Path(archive_path).open("rb") as source:
                while block := source.read(READ_CHUNK):
                    encrypted_stream.write(block)
            encrypted_stream.finish()
            destination.flush()
            os.fsync(destination.fileno())
        temporary_archive.chmod(0o600)
        try:
            os.link(temporary_archive, output_path)
        except FileExistsError as error:
            raise BackupError(f"Không ghi đè backup đã tồn tại: {output_path}") from error
        output_created = True
        verify_backup(output_path, passphrase)
        output_created = False
        return output_path
    finally:
        temporary_archive.unlink(missing_ok=True)
        if output_created:
            output_path.unlink(missing_ok=True)


def decrypt_backup(encrypted_path: Path, output_path: Path, passphrase: str) -> Path:
    output_path = output_path.expanduser().resolve()
    if not output_path.parent.is_dir():
        raise BackupError("Thư mục đích giải mã không tồn tại.")
    try:
        plaintext_path = decrypt_to_private_temp(
            encrypted_path, passphrase, BACKUP_MAGIC, suffix=".tar.gz"
        )
    except ValueError as error:
        raise BackupError(str(error)) from error
    output_created = False
    try:
        _verify_plain_backup(plaintext_path)
        try:
            descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as error:
            raise BackupError(f"Không ghi đè backup đã tồn tại: {output_path}") from error
        output_created = True
        with os.fdopen(descriptor, "wb") as destination, plaintext_path.open("rb") as source:
            shutil.copyfileobj(source, destination, length=READ_CHUNK)
            destination.flush()
            os.fsync(destination.fileno())
        output_path.chmod(0o600)
        output_created = False
        return output_path
    finally:
        plaintext_path.unlink(missing_ok=True)
        if output_created:
            output_path.unlink(missing_ok=True)


def _default_backup_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ROOT_DIR / "backups" / f"petcare-{stamp}.pcarebackup"


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo và xác minh backup mã hóa cho PetCare Manager.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create", help="Backup mã hóa database MySQL và ảnh")
    create_parser.add_argument("--output", type=Path, default=_default_backup_path())
    create_parser.add_argument("--database", default=Config.DB_NAME)
    create_parser.add_argument("--media-source", choices=("host", "compose"), default="host")
    verify_parser = subparsers.add_parser("verify", help="Xác thực mã hóa, checksum và đường dẫn trong backup")
    verify_parser.add_argument("archive", type=Path)
    encrypt_parser = subparsers.add_parser("encrypt", help="Kiểm tra và mã hóa backup tar.gz cũ")
    encrypt_parser.add_argument("archive", type=Path)
    encrypt_parser.add_argument("output", type=Path)
    decrypt_parser = subparsers.add_parser("decrypt", help="Tạo tar.gz riêng tư để khôi phục")
    decrypt_parser.add_argument("archive", type=Path)
    decrypt_parser.add_argument("output", type=Path)
    args = parser.parse_args()

    try:
        if args.command == "create":
            passphrase = getpass.getpass("Chọn passphrase backup (ít nhất 12 ký tự): ")
            confirmation = getpass.getpass("Nhập lại passphrase backup: ")
            if passphrase != confirmation:
                raise BackupError("Hai passphrase không khớp.")
            result = create_backup(args.output, args.database, args.media_source, passphrase)
            print(f"Đã tạo backup mã hóa: {result} ({result.stat().st_size:,} bytes)")
        elif args.command == "verify":
            passphrase = getpass.getpass("Passphrase backup: ")
            result = verify_backup(args.archive, passphrase)
            print(
                "Backup hợp lệ: database={database}; tạo UTC={created_at_utc}; "
                "mục ảnh={media_entries}; kích thước={size_bytes:,} bytes".format(**result)
            )
        elif args.command == "encrypt":
            passphrase = getpass.getpass("Chọn passphrase backup (ít nhất 12 ký tự): ")
            confirmation = getpass.getpass("Nhập lại passphrase backup: ")
            if passphrase != confirmation:
                raise BackupError("Hai passphrase không khớp.")
            output = encrypt_legacy_backup(args.archive, args.output, passphrase)
            print(f"Backup cũ đã xác minh và mã hóa: {output}")
        else:
            passphrase = getpass.getpass("Passphrase backup: ")
            output = decrypt_backup(args.archive, args.output, passphrase)
            print(f"Backup đã xác thực và giải mã vào {output}; hãy giữ file riêng tư.")
    except (BackupError, OSError, ValueError) as error:
        print(f"Lỗi backup: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

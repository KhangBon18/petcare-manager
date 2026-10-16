"""Quản lý kết nối SQLite và giao dịch."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Generator

from petcare.config import DB_PATH, DATA_DIR


def get_connection(database_path: Path | str | None = None) -> sqlite3.Connection:
    """Mở kết nối tới SQLite database và luôn kích hoạt khóa ngoại."""
    uri = False
    if database_path is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        database_path = DB_PATH
    elif isinstance(database_path, str):
        if database_path.startswith("file:"):
            uri = True
        elif database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    elif isinstance(database_path, Path):
        database_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(database_path, uri=uri)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[sqlite3.Connection, None, None]:
    """Context manager cho transaction an toàn: tự commit nếu thành công, rollback nếu có lỗi."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise

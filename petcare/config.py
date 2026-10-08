"""Đường dẫn dùng chung, luôn tính từ vị trí mã nguồn."""

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
DB_PATH = DATA_DIR / "petcare.db"
ASSETS_DIR = PROJECT_DIR / "assets"

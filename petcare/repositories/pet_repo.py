"""Repository xử lý dữ liệu bảng pets (Thú cưng)."""

from datetime import datetime
import sqlite3
from typing import Any


class PetRepository:
    """Truy vấn SQL có tham số cho thú cưng. Nhận kết nối conn, không tự kết thúc transaction."""

    @staticmethod
    def create(
        conn: sqlite3.Connection,
        owner_id: int,
        name: str,
        species: str,
        breed: str | None = None,
        sex: str = "unknown",
        birth_date: str | None = None,
        weight_kg: float | None = None,
        coat_color: str | None = None,
    ) -> int:
        now_str = datetime.now().isoformat()
        cursor = conn.execute(
            """
            INSERT INTO pets (owner_id, name, species, breed, sex, birth_date, weight_kg, coat_color, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                owner_id,
                name.strip(),
                species.strip(),
                breed.strip() if breed else None,
                sex,
                birth_date.strip() if birth_date else None,
                weight_kg,
                coat_color.strip() if coat_color else None,
                now_str,
            ),
        )
        return cursor.lastrowid

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, pet_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT p.*, o.full_name AS owner_name, o.phone AS owner_phone
            FROM pets p
            JOIN owners o ON p.owner_id = o.id
            WHERE p.id = ?
            """,
            (pet_id,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_by_owner_id(
        conn: sqlite3.Connection, owner_id: int, active_only: bool = True
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM pets WHERE owner_id = ?"
        if active_only:
            query += " AND active = 1"
        query += " ORDER BY id DESC"
        rows = conn.execute(query, (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def update(
        conn: sqlite3.Connection,
        pet_id: int,
        name: str,
        species: str,
        breed: str | None = None,
        sex: str = "unknown",
        birth_date: str | None = None,
        weight_kg: float | None = None,
        coat_color: str | None = None,
        active: int = 1,
        owner_id: int | None = None,
    ) -> bool:
        if owner_id is not None:
            cursor = conn.execute(
                """
                UPDATE pets
                SET name = ?, species = ?, breed = ?, sex = ?, birth_date = ?, weight_kg = ?, coat_color = ?, active = ?, owner_id = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    species.strip(),
                    breed.strip() if breed else None,
                    sex,
                    birth_date.strip() if birth_date else None,
                    weight_kg,
                    coat_color.strip() if coat_color else None,
                    active,
                    owner_id,
                    pet_id,
                ),
            )
        else:
            cursor = conn.execute(
                """
                UPDATE pets
                SET name = ?, species = ?, breed = ?, sex = ?, birth_date = ?, weight_kg = ?, coat_color = ?, active = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    species.strip(),
                    breed.strip() if breed else None,
                    sex,
                    birth_date.strip() if birth_date else None,
                    weight_kg,
                    coat_color.strip() if coat_color else None,
                    active,
                    pet_id,
                ),
            )
        return cursor.rowcount > 0

    @staticmethod
    def search(
        conn: sqlite3.Connection,
        keyword: str = "",
        species: str = "",
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT p.*, o.full_name AS owner_name, o.phone AS owner_phone
            FROM pets p
            JOIN owners o ON p.owner_id = o.id
            WHERE 1=1
        """
        params: list[Any] = []

        if active_only:
            query += " AND p.active = 1"

        if species and species.strip():
            query += " AND p.species = ?"
            params.append(species.strip())

        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            query += " AND (p.name LIKE ? OR p.breed LIKE ? OR o.full_name LIKE ? OR o.phone LIKE ?)"
            params.extend([kw, kw, kw, kw])

        query += " ORDER BY p.id DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def list_all(conn: sqlite3.Connection, active_only: bool = True) -> list[dict[str, Any]]:
        return PetRepository.search(conn, keyword="", species="", active_only=active_only)

    @staticmethod
    def has_history(conn: sqlite3.Connection, pet_id: int) -> bool:
        """Kiểm tra thú cưng đã có hồ sơ y tế, lịch hẹn hoặc lượt dịch vụ hay chưa."""
        visits = conn.execute(
            "SELECT COUNT(*) as cnt FROM service_visits WHERE pet_id = ?",
            (pet_id,),
        ).fetchone()["cnt"]
        if visits > 0:
            return True

        appts = conn.execute(
            "SELECT COUNT(*) as cnt FROM appointments WHERE pet_id = ?",
            (pet_id,),
        ).fetchone()["cnt"]
        return appts > 0

    @staticmethod
    def has_invoices(conn: sqlite3.Connection, pet_id: int) -> bool:
        """Kiểm tra thú cưng đã có hóa đơn liên quan hay chưa."""
        row = conn.execute(
            """
            SELECT COUNT(*) as cnt
            FROM invoice_items ii
            JOIN service_visits sv ON ii.visit_id = sv.id
            WHERE sv.pet_id = ?
            """,
            (pet_id,),
        ).fetchone()
        return (row["cnt"] if row else 0) > 0

    @staticmethod
    def deactivate(conn: sqlite3.Connection, pet_id: int) -> bool:
        cursor = conn.execute(
            "UPDATE pets SET active = 0 WHERE id = ?",
            (pet_id,),
        )
        return cursor.rowcount > 0

    @staticmethod
    def delete(conn: sqlite3.Connection, pet_id: int) -> bool:
        cursor = conn.execute(
            "DELETE FROM pets WHERE id = ?",
            (pet_id,),
        )
        return cursor.rowcount > 0

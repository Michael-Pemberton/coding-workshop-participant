"""Data access layer for people."""

import logging
from typing import Optional

import psycopg

logger = logging.getLogger(__name__)


class PersonRepository:
    """Handles all database operations for the people table."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def _row_to_dict(self, cursor: psycopg.Cursor, row: tuple) -> dict:
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row))

    def find_all(self, is_active: Optional[bool] = None, search: Optional[str] = None) -> list[dict]:
        """Returns all non-deleted people with optional filters."""
        conditions = ["is_deleted = FALSE"]
        params: list = []
        if is_active is not None:
            conditions.append("is_active = %s")
            params.append(is_active)
        if search:
            conditions.append("(LOWER(name) LIKE %s OR LOWER(email) LIKE %s)")
            params.extend([f"%{search.lower()}%", f"%{search.lower()}%"])
        query = f"SELECT * FROM people WHERE {' AND '.join(conditions)} ORDER BY name"
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return [self._row_to_dict(cur, row) for row in cur.fetchall()]

    def find_by_id(self, person_id: str) -> Optional[dict]:
        """Returns a person by ID or None."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM people WHERE id = %s AND is_deleted = FALSE", (person_id,)
            )
            row = cur.fetchone()
            return self._row_to_dict(cur, row) if row else None

    def find_by_email(self, email: str) -> Optional[dict]:
        """Returns an active person by email or None."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM people WHERE email = %s AND is_deleted = FALSE", (email,)
            )
            row = cur.fetchone()
            return self._row_to_dict(cur, row) if row else None

    def create(self, data: dict) -> dict:
        """Inserts a new person and returns the created record."""
        cols = list(data.keys())
        vals = list(data.values())
        placeholders = ", ".join(["%s"] * len(vals))
        query = f"INSERT INTO people ({', '.join(cols)}) VALUES ({placeholders}) RETURNING *"
        with self.conn.cursor() as cur:
            cur.execute(query, vals)
            row = cur.fetchone()
            self.conn.commit()
            return self._row_to_dict(cur, row)

    def update(self, person_id: str, data: dict) -> Optional[dict]:
        """Updates person fields and returns the updated record."""
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        vals = list(data.values()) + [person_id]
        query = (
            f"UPDATE people SET {set_clause}, updated_at = NOW() "
            f"WHERE id = %s AND is_deleted = FALSE RETURNING *"
        )
        with self.conn.cursor() as cur:
            cur.execute(query, vals)
            row = cur.fetchone()
            self.conn.commit()
            return self._row_to_dict(cur, row) if row else None

    def delete(self, person_id: str) -> bool:
        """Soft-deletes a person record."""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE people SET is_deleted = TRUE, updated_at = NOW() "
                "WHERE id = %s AND is_deleted = FALSE",
                (person_id,),
            )
            self.conn.commit()
            return cur.rowcount > 0

    def find_with_allocation(self, person_id: str) -> Optional[dict]:
        """Returns a person enriched with total allocated_hours_per_week and overallocation flag."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.*,
                       COALESCE(SUM(a.hours_per_week), 0) AS allocated_hours_per_week
                FROM people p
                LEFT JOIN assignments a ON a.person_id = p.id AND a.is_deleted = FALSE
                WHERE p.id = %s AND p.is_deleted = FALSE
                GROUP BY p.id
                """,
                (person_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            result = self._row_to_dict(cur, row)
            result["is_overallocated"] = (
                result["allocated_hours_per_week"] > result["weekly_hours_capacity"]
            )
            return result

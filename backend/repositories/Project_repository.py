"""Data access layer for projects."""

import logging
from typing import Optional

import psycopg

logger = logging.getLogger(__name__)


class ProjectRepository:
    """Handles all database operations for the projects table."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def _row_to_dict(self, cursor: psycopg.Cursor, row: tuple) -> dict:
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row))

    def find_all(
        self,
        status: Optional[str] = None,
        health: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[dict]:
        """Returns all non-deleted projects with optional filters."""
        conditions = ["is_deleted = FALSE"]
        params: list = []
        if status:
            conditions.append("status = %s")
            params.append(status)
        if health:
            conditions.append("health = %s")
            params.append(health)
        if search:
            conditions.append("LOWER(title) LIKE %s")
            params.append(f"%{search.lower()}%")
        query = (
            f"SELECT * FROM projects WHERE {' AND '.join(conditions)} ORDER BY created_at DESC"
        )
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return [self._row_to_dict(cur, row) for row in cur.fetchall()]

    def find_by_id(self, project_id: str) -> Optional[dict]:
        """Returns a project by ID or None if not found / soft-deleted."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM projects WHERE id = %s AND is_deleted = FALSE",
                (project_id,),
            )
            row = cur.fetchone()
            return self._row_to_dict(cur, row) if row else None

    def create(self, data: dict) -> dict:
        """Inserts a new project row and returns the created record."""
        cols = list(data.keys())
        vals = list(data.values())
        placeholders = ", ".join(["%s"] * len(vals))
        query = (
            f"INSERT INTO projects ({', '.join(cols)}) VALUES ({placeholders}) RETURNING *"
        )
        with self.conn.cursor() as cur:
            cur.execute(query, vals)
            row = cur.fetchone()
            self.conn.commit()
            return self._row_to_dict(cur, row)

    def update(self, project_id: str, data: dict) -> Optional[dict]:
        """Updates specified fields of a project and returns the updated record."""
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        vals = list(data.values()) + [project_id]
        query = (
            f"UPDATE projects SET {set_clause}, updated_at = NOW() "
            f"WHERE id = %s AND is_deleted = FALSE RETURNING *"
        )
        with self.conn.cursor() as cur:
            cur.execute(query, vals)
            row = cur.fetchone()
            self.conn.commit()
            return self._row_to_dict(cur, row) if row else None

    def delete(self, project_id: str) -> bool:
        """Soft-deletes a project by setting is_deleted = TRUE."""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE projects SET is_deleted = TRUE, updated_at = NOW() "
                "WHERE id = %s AND is_deleted = FALSE",
                (project_id,),
            )
            self.conn.commit()
            return cur.rowcount > 0

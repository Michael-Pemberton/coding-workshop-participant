"""Data access layer for project deliverables."""

import logging
from typing import Optional
import psycopg

logger = logging.getLogger(__name__)


class DeliverableRepository:
    """Handles all database operations for the deliverables table."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def _row_to_dict(self, cursor: psycopg.Cursor, row: tuple) -> dict:
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row))

    def find_all(self, project_id: Optional[str] = None, status: Optional[str] = None) -> list[dict]:
        """Returns all non-deleted deliverables with optional filters."""
        conditions = ["d.is_deleted = FALSE"]
        params: list = []
        if project_id:
            conditions.append("d.project_id = %s")
            params.append(project_id)
        if status:
            conditions.append("d.status = %s")
            params.append(status)
        query = (
            f"SELECT d.*, dep.title AS depends_on_title "
            f"FROM deliverables d "
            f"LEFT JOIN deliverables dep ON dep.id = d.depends_on_id "
            f"WHERE {' AND '.join(conditions)} ORDER BY d.created_at"
        )
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return [self._row_to_dict(cur, row) for row in cur.fetchall()]

    def find_by_id(self, deliverable_id: str) -> Optional[dict]:
        """Returns a deliverable with its dependency title."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT d.*, dep.title AS depends_on_title "
                "FROM deliverables d "
                "LEFT JOIN deliverables dep ON dep.id = d.depends_on_id "
                "WHERE d.id = %s AND d.is_deleted = FALSE",
                (deliverable_id,),
            )
            row = cur.fetchone()
            return self._row_to_dict(cur, row) if row else None

    def create(self, data: dict) -> dict:
        """Inserts a new deliverable and returns the created record."""
        cols = list(data.keys())
        vals = list(data.values())
        placeholders = ", ".join(["%s"] * len(vals))
        query = f"INSERT INTO deliverables ({', '.join(cols)}) VALUES ({placeholders}) RETURNING *"
        with self.conn.cursor() as cur:
            cur.execute(query, vals)
            row = cur.fetchone()
            self.conn.commit()
            return self._row_to_dict(cur, row)

    def update(self, deliverable_id: str, data: dict) -> Optional[dict]:
        """Updates deliverable fields and returns the updated record."""
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        vals = list(data.values()) + [deliverable_id]
        query = (
            f"UPDATE deliverables SET {set_clause}, updated_at = NOW() "
            f"WHERE id = %s AND is_deleted = FALSE RETURNING *"
        )
        with self.conn.cursor() as cur:
            cur.execute(query, vals)
            row = cur.fetchone()
            self.conn.commit()
            return self._row_to_dict(cur, row) if row else None

    def delete(self, deliverable_id: str) -> bool:
        """Soft-deletes a deliverable."""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE deliverables SET is_deleted = TRUE, updated_at = NOW() "
                "WHERE id = %s AND is_deleted = FALSE",
                (deliverable_id,),
            )
            self.conn.commit()
            return cur.rowcount > 0

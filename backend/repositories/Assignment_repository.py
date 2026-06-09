"""Data access layer for person-project assignments."""

import logging
from typing import Optional
import psycopg

logger = logging.getLogger(__name__)


class AssignmentRepository:
    """Handles all database operations for the assignments table."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def _row_to_dict(self, cursor: psycopg.Cursor, row: tuple) -> dict:
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row))

    def find_all(self, project_id: Optional[str] = None, person_id: Optional[str] = None) -> list[dict]:
        """Returns all non-deleted assignments with optional filters."""
        conditions = ["a.is_deleted = FALSE"]
        params: list = []
        if project_id:
            conditions.append("a.project_id = %s")
            params.append(project_id)
        if person_id:
            conditions.append("a.person_id = %s")
            params.append(person_id)
        query = (
            f"SELECT a.*, p.name AS person_name, p.email AS person_email, "
            f"pr.title AS project_title "
            f"FROM assignments a "
            f"LEFT JOIN people p ON p.id = a.person_id "
            f"LEFT JOIN projects pr ON pr.id = a.project_id "
            f"WHERE {' AND '.join(conditions)} ORDER BY a.created_at DESC"
        )
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return [self._row_to_dict(cur, row) for row in cur.fetchall()]

    def find_by_id(self, assignment_id: str) -> Optional[dict]:
        """Returns an assignment with person and project names."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT a.*, p.name AS person_name, pr.title AS project_title "
                "FROM assignments a "
                "LEFT JOIN people p ON p.id = a.person_id "
                "LEFT JOIN projects pr ON pr.id = a.project_id "
                "WHERE a.id = %s AND a.is_deleted = FALSE",
                (assignment_id,),
            )
            row = cur.fetchone()
            return self._row_to_dict(cur, row) if row else None

    def find_by_person_and_project(self, person_id: str, project_id: str) -> Optional[dict]:
        """Returns an existing active assignment for the given person+project pair."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM assignments WHERE person_id = %s AND project_id = %s AND is_deleted = FALSE",
                (person_id, project_id),
            )
            row = cur.fetchone()
            return self._row_to_dict(cur, row) if row else None

    def create(self, data: dict) -> dict:
        """Inserts a new assignment and returns the created record."""
        cols = list(data.keys())
        vals = list(data.values())
        placeholders = ", ".join(["%s"] * len(vals))
        query = f"INSERT INTO assignments ({', '.join(cols)}) VALUES ({placeholders}) RETURNING *"
        with self.conn.cursor() as cur:
            cur.execute(query, vals)
            row = cur.fetchone()
            self.conn.commit()
            return self._row_to_dict(cur, row)

    def update(self, assignment_id: str, data: dict) -> Optional[dict]:
        """Updates assignment fields and returns the updated record."""
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        vals = list(data.values()) + [assignment_id]
        query = (
            f"UPDATE assignments SET {set_clause}, updated_at = NOW() "
            f"WHERE id = %s AND is_deleted = FALSE RETURNING *"
        )
        with self.conn.cursor() as cur:
            cur.execute(query, vals)
            row = cur.fetchone()
            self.conn.commit()
            return self._row_to_dict(cur, row) if row else None

    def delete(self, assignment_id: str) -> bool:
        """Soft-deletes an assignment."""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE assignments SET is_deleted = TRUE, updated_at = NOW() "
                "WHERE id = %s AND is_deleted = FALSE",
                (assignment_id,),
            )
            self.conn.commit()
            return cur.rowcount > 0

    def get_person_total_hours(self, person_id: str) -> int:
        """Returns total allocated hours per week across all active assignments for a person."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(hours_per_week), 0) FROM assignments "
                "WHERE person_id = %s AND is_deleted = FALSE",
                (person_id,),
            )
            return int(cur.fetchone()[0])

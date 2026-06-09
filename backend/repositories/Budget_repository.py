"""Data access layer for project budget items."""

import logging
from typing import Optional
import psycopg

logger = logging.getLogger(__name__)


class BudgetRepository:
    """Handles all database operations for the budget_items table."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def _row_to_dict(self, cursor: psycopg.Cursor, row: tuple) -> dict:
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row))

    def find_all(self, project_id: Optional[str] = None) -> list[dict]:
        """Returns all non-deleted budget items, optionally filtered by project."""
        conditions = ["is_deleted = FALSE"]
        params: list = []
        if project_id:
            conditions.append("project_id = %s")
            params.append(project_id)
        query = (
            f"SELECT * FROM budget_items WHERE {' AND '.join(conditions)} ORDER BY created_at DESC"
        )
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return [self._row_to_dict(cur, row) for row in cur.fetchall()]

    def find_by_id(self, budget_id: str) -> Optional[dict]:
        """Returns a budget item by ID or None."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM budget_items WHERE id = %s AND is_deleted = FALSE", (budget_id,)
            )
            row = cur.fetchone()
            return self._row_to_dict(cur, row) if row else None

    def create(self, data: dict) -> dict:
        """Inserts a new budget item and returns the created record."""
        cols = list(data.keys())
        vals = list(data.values())
        placeholders = ", ".join(["%s"] * len(vals))
        query = f"INSERT INTO budget_items ({', '.join(cols)}) VALUES ({placeholders}) RETURNING *"
        with self.conn.cursor() as cur:
            cur.execute(query, vals)
            row = cur.fetchone()
            self.conn.commit()
            return self._row_to_dict(cur, row)

    def update(self, budget_id: str, data: dict) -> Optional[dict]:
        """Updates budget item fields and returns the updated record."""
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        vals = list(data.values()) + [budget_id]
        query = (
            f"UPDATE budget_items SET {set_clause}, updated_at = NOW() "
            f"WHERE id = %s AND is_deleted = FALSE RETURNING *"
        )
        with self.conn.cursor() as cur:
            cur.execute(query, vals)
            row = cur.fetchone()
            self.conn.commit()
            return self._row_to_dict(cur, row) if row else None

    def delete(self, budget_id: str) -> bool:
        """Soft-deletes a budget item."""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE budget_items SET is_deleted = TRUE, updated_at = NOW() "
                "WHERE id = %s AND is_deleted = FALSE",
                (budget_id,),
            )
            self.conn.commit()
            return cur.rowcount > 0

    def get_project_totals(self, project_id: str) -> dict:
        """Returns aggregated planned/consumed totals for a project's budget items."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(amount_planned), 0), COALESCE(SUM(amount_consumed), 0) "
                "FROM budget_items WHERE project_id = %s AND is_deleted = FALSE",
                (project_id,),
            )
            row = cur.fetchone()
            return {"total_planned": row[0], "total_consumed": row[1]}

    def sync_project_budget(self, project_id: str) -> None:
        """Recalculates and writes the project budget_consumed from sum of active budget items."""
        totals = self.get_project_totals(project_id)
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE projects SET budget_consumed = %s, updated_at = NOW() WHERE id = %s",
                (totals["total_consumed"], project_id),
            )
        self.conn.commit()

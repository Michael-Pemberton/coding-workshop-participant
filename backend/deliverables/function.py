"""Deliverables Lambda — CRUD for project deliverables."""

import json
import logging
from datetime import date

from shared import (
    get_db, resp, get_user, extract_id, rows_to_dicts, row_to_dict,
    filter_fields, get_scoped_project_ids,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_MAX_DEP_DEPTH = 100


def _as_date(v):
    if not v:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _time_rag(due) -> tuple[str, str]:
    """RAG from due date alone. Returns (color, reason)."""
    d = _as_date(due)
    if not d:
        return "green", "No due date set"
    days = (d - date.today()).days
    if days < 0:
        return "red", f"Overdue by {-days} day(s)"
    if days <= 1:
        return "red", f"Due in {days} day(s)"
    if days <= 5:
        return "amber", f"Due in {days} day(s)"
    return "green", f"Due in {days} day(s)"


_WORSE = {"green": 0, "amber": 1, "red": 2}


def _with_rag(row: dict) -> dict:
    """Computes status + health_reason from due_date, then:
    - appends "; Depends on \"X\"" when this row has a prerequisite;
    - worsens to the prerequisite's time-band if worse (forward propagation);
    - worsens to the earliest dependant's time-band if worse (reverse propagation).
    Worsening uses "<color> due to prerequisite/dependant due in N day(s)"."""
    if row is None:
        return row
    color, reason = _time_rag(row.get("due_date"))
    own_due = _as_date(row.get("due_date"))

    dep_title = row.get("depends_on_title")
    dep_due = _as_date(row.get("depends_on_due_date"))
    if dep_title:
        reason = f"{reason}; Depends on \"{dep_title}\""

    if dep_due:
        d_color, _ = _time_rag(dep_due)
        if _WORSE[d_color] > _WORSE[color]:
            days = (dep_due - date.today()).days
            color = d_color
            reason = (
                f"{d_color} due to prerequisite overdue by {-days} day(s)"
                if days < 0
                else f"{d_color} due to prerequisite due in {days} day(s)"
            )

    earliest_dep = _as_date(row.get("earliest_dependant_due"))
    if earliest_dep and (own_due is None or earliest_dep < own_due):
        d_color, _ = _time_rag(earliest_dep)
        if _WORSE[d_color] > _WORSE[color]:
            days = (earliest_dep - date.today()).days
            color = d_color
            reason = (
                f"{d_color} due to dependant overdue by {-days} day(s)"
                if days < 0
                else f"{d_color} due to dependant due in {days} day(s)"
            )

    row["status"] = color
    row["health_reason"] = reason
    return row


def _would_cycle(conn, item_id: str | None, depends_on_id: str | None) -> bool:
    """Walks the dependency chain starting at depends_on_id; returns True if it
    revisits item_id or exceeds max depth (treating that as a cycle)."""
    if not depends_on_id:
        return False
    if item_id and depends_on_id == item_id:
        return True
    visited = set()
    current = depends_on_id
    with conn.cursor() as cur:
        for _ in range(_MAX_DEP_DEPTH):
            if not current or current in visited:
                return current in visited
            if item_id and current == item_id:
                return True
            visited.add(current)
            cur.execute(
                "SELECT depends_on_id FROM deliverables WHERE id = %s AND is_deleted = FALSE",
                (current,),
            )
            row = cur.fetchone()
            if not row:
                return False
            current = str(row[0]) if row[0] else None
    return True


def _validate_deliverable(body: dict) -> str | None:
    due_date = body.get("due_date")
    if due_date is not None:
        try:
            date.fromisoformat(str(due_date)[:10])
        except ValueError:
            return "due_date must be a valid ISO date (YYYY-MM-DD)"
    return None


_SELECT_BASE = (
    "SELECT d.*, dep.title AS depends_on_title, dep.due_date AS depends_on_due_date, "
    "dep_proj.title AS depends_on_project_title, "
    "(SELECT MIN(due_date) FROM deliverables "
    " WHERE depends_on_id = d.id AND is_deleted = FALSE) AS earliest_dependant_due, "
    "(SELECT title FROM deliverables "
    " WHERE depends_on_id = d.id AND is_deleted = FALSE AND due_date IS NOT NULL "
    " ORDER BY due_date ASC LIMIT 1) AS earliest_dependant_title "
    "FROM deliverables d "
    "LEFT JOIN deliverables dep ON dep.id = d.depends_on_id "
    "LEFT JOIN projects dep_proj ON dep_proj.id = dep.project_id "
)


def handler(event=None, context=None):
    """Routes deliverable CRUD requests."""
    if event is None:
        event = {}
    method = (event.get("requestContext") or {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "")

    if method == "OPTIONS":
        return resp(204, {})

    user = get_user(event)
    if not user:
        return resp(401, {"error": "Authentication required", "success": False})

    item_id = extract_id(path)
    params = event.get("queryStringParameters") or {}
    conn = get_db()
    scope_ids = get_scoped_project_ids(conn, user)

    try:
        if method == "GET" and not item_id:
            conditions = ["d.is_deleted = FALSE"]
            vals: list = []
            if params.get("project_id"):
                if scope_ids is not None and params["project_id"] not in scope_ids:
                    return resp(200, {"data": [], "success": True})
                conditions.append("d.project_id = %s")
                vals.append(params["project_id"])
            elif scope_ids is not None:
                if not scope_ids:
                    return resp(200, {"data": [], "success": True})
                conditions.append("d.project_id = ANY(%s)")
                vals.append(scope_ids)
            try:
                limit = min(int(params.get("limit", 100)), 500)
                offset = int(params.get("offset", 0))
            except (TypeError, ValueError):
                return resp(400, {"error": "limit and offset must be integers", "success": False})
            with conn.cursor() as cur:
                cur.execute(
                    f"{_SELECT_BASE} WHERE {' AND '.join(conditions)} "
                    f"ORDER BY d.created_at LIMIT %s OFFSET %s",
                    vals + [limit, offset],
                )
                items = [_with_rag(r) for r in rows_to_dicts(cur)]
                if params.get("status") in ("red", "amber", "green"):
                    items = [i for i in items if i["status"] == params["status"]]
                return resp(200, {"data": items, "success": True})

        if method == "GET" and item_id:
            with conn.cursor() as cur:
                cur.execute(f"{_SELECT_BASE} WHERE d.id = %s AND d.is_deleted = FALSE", (item_id,))
                row = cur.fetchone()
                if not row:
                    return resp(404, {"error": "Deliverable not found", "success": False})
                item = _with_rag(row_to_dict(cur, row))
                if scope_ids is not None and str(item.get("project_id")) not in scope_ids:
                    return resp(404, {"error": "Deliverable not found", "success": False})
                return resp(200, {"data": item, "success": True})

        if method == "POST":
            if user.get("role") not in ("admin", "manager", "contributor"):
                return resp(403, {"error": "Insufficient permissions", "success": False})
            body = json.loads(event.get("body") or "{}")
            if not body.get("title", "").strip():
                return resp(400, {"error": "title is required", "success": False})
            if not body.get("project_id"):
                return resp(400, {"error": "project_id is required", "success": False})
            body = filter_fields("deliverables", body)
            body.pop("status", None)
            err = _validate_deliverable(body)
            if err:
                return resp(400, {"error": err, "success": False})
            if body.get("depends_on_id") and _would_cycle(conn, None, body["depends_on_id"]):
                return resp(400, {"error": "This dependency would create a cycle", "success": False})
            cols = list(body.keys())
            vals2 = list(body.values())
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO deliverables ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(vals2))}) RETURNING id",
                    vals2,
                )
                new_id = cur.fetchone()[0]
                conn.commit()
                cur.execute(f"{_SELECT_BASE} WHERE d.id = %s", (new_id,))
                row = cur.fetchone()
                return resp(201, {"data": _with_rag(row_to_dict(cur, row)), "success": True})

        if method == "PUT" and item_id:
            if user.get("role") not in ("admin", "manager", "contributor"):
                return resp(403, {"error": "Insufficient permissions", "success": False})
            body = json.loads(event.get("body") or "{}")
            body = filter_fields("deliverables", body)
            body.pop("status", None)
            err = _validate_deliverable(body)
            if err:
                return resp(400, {"error": err, "success": False})
            if not body:
                return resp(400, {"error": "No valid fields to update", "success": False})
            if "depends_on_id" in body and body["depends_on_id"] and _would_cycle(conn, item_id, body["depends_on_id"]):
                return resp(400, {"error": "This dependency would create a cycle", "success": False})
            set_clause = ", ".join([f"{k} = %s" for k in body.keys()])
            vals3 = list(body.values()) + [item_id]
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE deliverables SET {set_clause}, updated_at = NOW() WHERE id = %s AND is_deleted = FALSE RETURNING id",
                    vals3,
                )
                row = cur.fetchone()
                conn.commit()
                if not row:
                    return resp(404, {"error": "Deliverable not found", "success": False})
                cur.execute(f"{_SELECT_BASE} WHERE d.id = %s", (item_id,))
                row = cur.fetchone()
                return resp(200, {"data": _with_rag(row_to_dict(cur, row)), "success": True})

        if method == "DELETE" and item_id:
            if user.get("role") not in ("admin", "manager"):
                return resp(403, {"error": "Insufficient permissions", "success": False})
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE deliverables SET is_deleted = TRUE, updated_at = NOW() WHERE id = %s AND is_deleted = FALSE",
                    (item_id,),
                )
                conn.commit()
                if cur.rowcount == 0:
                    return resp(404, {"error": "Deliverable not found", "success": False})
            return resp(204, {})

        return resp(405, {"error": "Method not allowed", "success": False})
    except Exception as exc:
        logger.error("Error: %s", exc, exc_info=True)
        return resp(500, {"error": f"{type(exc).__name__}: {exc}", "success": False})


if __name__ == "__main__":
    print(handler({"requestContext": {"http": {"method": "GET"}}, "rawPath": "/api/deliverables"}))

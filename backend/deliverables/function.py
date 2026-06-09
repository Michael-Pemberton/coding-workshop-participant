"""Deliverables Lambda — CRUD for project deliverables."""

import json
import logging

from shared import (
    get_db, resp, get_user, extract_id, rows_to_dicts, row_to_dict, init_db,
    filter_fields, VALID_DELIVERABLE_STATUSES,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

try:
    init_db()
except Exception as exc:
    logger.error("DB init failed: %s", exc)


def _validate_deliverable(body: dict) -> str | None:
    """Returns an error string if the body is invalid, else None."""
    status = body.get("status")
    if status is not None and status not in VALID_DELIVERABLE_STATUSES:
        return f"status must be one of: {sorted(VALID_DELIVERABLE_STATUSES)}"
    due_date = body.get("due_date")
    if due_date is not None:
        try:
            from datetime import date
            date.fromisoformat(str(due_date)[:10])
        except ValueError:
            return "due_date must be a valid ISO date (YYYY-MM-DD)"
    return None


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

    try:
        if method == "GET" and not item_id:
            conditions = ["d.is_deleted = FALSE"]
            vals: list = []
            if params.get("project_id"):
                conditions.append("d.project_id = %s")
                vals.append(params["project_id"])
            if params.get("status"):
                if params["status"] not in VALID_DELIVERABLE_STATUSES:
                    return resp(400, {"error": f"status must be one of: {sorted(VALID_DELIVERABLE_STATUSES)}", "success": False})
                conditions.append("d.status = %s")
                vals.append(params["status"])
            try:
                limit = min(int(params.get("limit", 100)), 500)
                offset = int(params.get("offset", 0))
            except (TypeError, ValueError):
                return resp(400, {"error": "limit and offset must be integers", "success": False})
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT d.*, dep.title AS depends_on_title "
                    f"FROM deliverables d LEFT JOIN deliverables dep ON dep.id = d.depends_on_id "
                    f"WHERE {' AND '.join(conditions)} ORDER BY d.created_at LIMIT %s OFFSET %s",
                    vals + [limit, offset],
                )
                return resp(200, {"data": rows_to_dicts(cur), "success": True})

        if method == "GET" and item_id:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT d.*, dep.title AS depends_on_title "
                    "FROM deliverables d LEFT JOIN deliverables dep ON dep.id = d.depends_on_id "
                    "WHERE d.id = %s AND d.is_deleted = FALSE",
                    (item_id,),
                )
                row = cur.fetchone()
                if not row:
                    return resp(404, {"error": "Deliverable not found", "success": False})
                return resp(200, {"data": row_to_dict(cur, row), "success": True})

        if method == "POST":
            if user.get("role") not in ("admin", "manager", "contributor"):
                return resp(403, {"error": "Insufficient permissions", "success": False})
            body = json.loads(event.get("body") or "{}")
            if not body.get("title", "").strip():
                return resp(400, {"error": "title is required", "success": False})
            if not body.get("project_id"):
                return resp(400, {"error": "project_id is required", "success": False})
            body = filter_fields("deliverables", body)
            err = _validate_deliverable(body)
            if err:
                return resp(400, {"error": err, "success": False})
            cols = list(body.keys())
            vals2 = list(body.values())
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO deliverables ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(vals2))}) RETURNING *",
                    vals2,
                )
                row = cur.fetchone()
                conn.commit()
                return resp(201, {"data": row_to_dict(cur, row), "success": True})

        if method == "PUT" and item_id:
            if user.get("role") not in ("admin", "manager", "contributor"):
                return resp(403, {"error": "Insufficient permissions", "success": False})
            body = json.loads(event.get("body") or "{}")
            body = filter_fields("deliverables", body)
            err = _validate_deliverable(body)
            if err:
                return resp(400, {"error": err, "success": False})
            if not body:
                return resp(400, {"error": "No valid fields to update", "success": False})
            set_clause = ", ".join([f"{k} = %s" for k in body.keys()])
            vals3 = list(body.values()) + [item_id]
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE deliverables SET {set_clause}, updated_at = NOW() WHERE id = %s AND is_deleted = FALSE RETURNING *",
                    vals3,
                )
                row = cur.fetchone()
                conn.commit()
                if not row:
                    return resp(404, {"error": "Deliverable not found", "success": False})
                return resp(200, {"data": row_to_dict(cur, row), "success": True})

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
        return resp(500, {"error": "Internal server error", "success": False})


if __name__ == "__main__":
    print(handler({"requestContext": {"http": {"method": "GET"}}, "rawPath": "/api/deliverables"}))

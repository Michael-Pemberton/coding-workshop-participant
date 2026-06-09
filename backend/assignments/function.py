"""Assignments Lambda — manage person-project allocations."""

import json
import logging

from shared import (
    get_db, resp, get_user, extract_id, rows_to_dicts, row_to_dict, init_db,
    filter_fields, UUID_RE,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

try:
    init_db()
except Exception as exc:
    logger.error("DB init failed: %s", exc)

# Validated integer fields and their allowed range.
_INT_FIELDS = {"hours_per_week": (0, 168)}


def _validate_assignment(body: dict) -> str | None:
    """Returns an error string if the body is invalid, else None."""
    hpw = body.get("hours_per_week")
    if hpw is not None:
        try:
            hpw = int(hpw)
        except (TypeError, ValueError):
            return "hours_per_week must be an integer"
        if not (0 <= hpw <= 168):
            return "hours_per_week must be between 0 and 168"
    for date_field in ("start_date", "end_date"):
        val = body.get(date_field)
        if val is not None:
            try:
                from datetime import date
                date.fromisoformat(str(val)[:10])
            except ValueError:
                return f"{date_field} must be a valid ISO date (YYYY-MM-DD)"
    for uuid_field in ("person_id", "project_id"):
        val = body.get(uuid_field)
        if val and not UUID_RE.match(str(val)):
            return f"{uuid_field} must be a valid UUID"
    return None


def handler(event=None, context=None):
    """Routes assignment CRUD requests."""
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
            conditions = ["a.is_deleted = FALSE"]
            vals: list = []
            if params.get("project_id"):
                conditions.append("a.project_id = %s")
                vals.append(params["project_id"])
            if params.get("person_id"):
                conditions.append("a.person_id = %s")
                vals.append(params["person_id"])
            # Pagination
            try:
                limit = min(int(params.get("limit", 100)), 500)
                offset = int(params.get("offset", 0))
            except (TypeError, ValueError):
                return resp(400, {"error": "limit and offset must be integers", "success": False})
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT a.*, p.name AS person_name, p.email AS person_email, pr.title AS project_title "
                    f"FROM assignments a "
                    f"LEFT JOIN people p ON p.id = a.person_id "
                    f"LEFT JOIN projects pr ON pr.id = a.project_id "
                    f"WHERE {' AND '.join(conditions)} "
                    f"ORDER BY a.created_at DESC LIMIT %s OFFSET %s",
                    vals + [limit, offset],
                )
                return resp(200, {"data": rows_to_dicts(cur), "success": True})

        if method == "GET" and item_id:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT a.*, p.name AS person_name, pr.title AS project_title "
                    "FROM assignments a "
                    "LEFT JOIN people p ON p.id = a.person_id "
                    "LEFT JOIN projects pr ON pr.id = a.project_id "
                    "WHERE a.id = %s AND a.is_deleted = FALSE",
                    (item_id,),
                )
                row = cur.fetchone()
                if not row:
                    return resp(404, {"error": "Assignment not found", "success": False})
                return resp(200, {"data": row_to_dict(cur, row), "success": True})

        if method == "POST":
            if user.get("role") not in ("admin", "manager"):
                return resp(403, {"error": "Insufficient permissions", "success": False})
            body = json.loads(event.get("body") or "{}")
            if not body.get("person_id") or not body.get("project_id"):
                return resp(400, {"error": "person_id and project_id are required", "success": False})
            body = filter_fields("assignments", body)
            err = _validate_assignment(body)
            if err:
                return resp(400, {"error": err, "success": False})
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM assignments WHERE person_id = %s AND project_id = %s AND is_deleted = FALSE",
                    (body["person_id"], body["project_id"]),
                )
                if cur.fetchone():
                    return resp(400, {"error": "Person is already assigned to this project", "success": False})
            cols = list(body.keys())
            vals2 = list(body.values())
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO assignments ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(vals2))}) RETURNING *",
                    vals2,
                )
                row = cur.fetchone()
                conn.commit()
                result = row_to_dict(cur, row)
            with conn.cursor() as cur2:
                cur2.execute(
                    "SELECT COALESCE(SUM(hours_per_week),0) FROM assignments WHERE person_id = %s AND is_deleted = FALSE",
                    (body["person_id"],),
                )
                total_hours = int(cur2.fetchone()[0])
                cur2.execute("SELECT weekly_hours_capacity FROM people WHERE id = %s", (body["person_id"],))
                capacity_row = cur2.fetchone()
                capacity = capacity_row[0] if capacity_row else 40
            result["overallocation_warning"] = total_hours > capacity
            result["total_allocated_hours"] = total_hours
            result["capacity"] = capacity
            return resp(201, {"data": result, "success": True})

        if method == "PUT" and item_id:
            if user.get("role") not in ("admin", "manager"):
                return resp(403, {"error": "Insufficient permissions", "success": False})
            body = json.loads(event.get("body") or "{}")
            body = filter_fields("assignments", body)
            err = _validate_assignment(body)
            if err:
                return resp(400, {"error": err, "success": False})
            if not body:
                return resp(400, {"error": "No valid fields to update", "success": False})
            set_clause = ", ".join([f"{k} = %s" for k in body.keys()])
            vals3 = list(body.values()) + [item_id]
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE assignments SET {set_clause}, updated_at = NOW() WHERE id = %s AND is_deleted = FALSE RETURNING *",
                    vals3,
                )
                row = cur.fetchone()
                conn.commit()
                if not row:
                    return resp(404, {"error": "Assignment not found", "success": False})
                return resp(200, {"data": row_to_dict(cur, row), "success": True})

        if method == "DELETE" and item_id:
            if user.get("role") not in ("admin", "manager"):
                return resp(403, {"error": "Insufficient permissions", "success": False})
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE assignments SET is_deleted = TRUE, updated_at = NOW() WHERE id = %s AND is_deleted = FALSE",
                    (item_id,),
                )
                conn.commit()
                if cur.rowcount == 0:
                    return resp(404, {"error": "Assignment not found", "success": False})
            return resp(204, {})

        return resp(405, {"error": "Method not allowed", "success": False})
    except Exception as exc:
        logger.error("Error: %s", exc, exc_info=True)
        return resp(500, {"error": "Internal server error", "success": False})


if __name__ == "__main__":
    print(handler({"requestContext": {"http": {"method": "GET"}}, "rawPath": "/api/assignments"}))

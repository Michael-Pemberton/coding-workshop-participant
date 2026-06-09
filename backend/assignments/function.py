"""Assignments Lambda — manage person-project allocations."""

import json
import logging

from shared import (
    get_db, resp, get_user, extract_id, rows_to_dicts, row_to_dict, init_db,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

try:
    init_db()
except Exception as exc:
    logger.error("DB init failed: %s", exc)


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
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT a.*, p.name AS person_name, p.email AS person_email, pr.title AS project_title FROM assignments a LEFT JOIN people p ON p.id = a.person_id LEFT JOIN projects pr ON pr.id = a.project_id WHERE {' AND '.join(conditions)} ORDER BY a.created_at DESC",
                    vals,
                )
                return resp(200, {"data": rows_to_dicts(cur), "success": True})

        if method == "GET" and item_id:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT a.*, p.name AS person_name, pr.title AS project_title FROM assignments a LEFT JOIN people p ON p.id = a.person_id LEFT JOIN projects pr ON pr.id = a.project_id WHERE a.id = %s AND a.is_deleted = FALSE",
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
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM assignments WHERE person_id = %s AND project_id = %s AND is_deleted = FALSE",
                    (body["person_id"], body["project_id"]),
                )
                if cur.fetchone():
                    return resp(400, {"error": "Person is already assigned to this project", "success": False})
            body.pop("id", None)
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
            body.pop("id", None)
            body.pop("created_at", None)
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

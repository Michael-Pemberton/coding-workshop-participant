"""People Lambda — CRUD with allocation tracking."""

import json
import logging
import re

from shared import (
    get_db, resp, get_user, extract_id, rows_to_dicts, row_to_dict, init_db,
    filter_fields,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

try:
    init_db()
except Exception as exc:
    logger.error("DB init failed: %s", exc)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_person(body: dict) -> str | None:
    """Returns an error string if the body is invalid, else None."""
    email = body.get("email")
    if email is not None and not _EMAIL_RE.match(str(email)):
        return "email must be a valid email address"
    cap = body.get("weekly_hours_capacity")
    if cap is not None:
        try:
            cap = int(cap)
            if not (1 <= cap <= 168):
                return "weekly_hours_capacity must be between 1 and 168"
        except (TypeError, ValueError):
            return "weekly_hours_capacity must be an integer"
    return None


def list_people(event: dict) -> dict:
    """GET /api/people — list all people with allocation info."""
    params = event.get("queryStringParameters") or {}
    try:
        limit = min(int(params.get("limit", 100)), 500)
        offset = int(params.get("offset", 0))
    except (TypeError, ValueError):
        return resp(400, {"error": "limit and offset must be integers", "success": False})
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.*,
                   COALESCE(SUM(a.hours_per_week), 0) AS allocated_hours_per_week
            FROM people p
            LEFT JOIN assignments a ON a.person_id = p.id AND a.is_deleted = FALSE
            WHERE p.is_deleted = FALSE
            GROUP BY p.id
            ORDER BY p.name
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        rows = rows_to_dicts(cur)
    for r in rows:
        r["is_overallocated"] = r.get("allocated_hours_per_week", 0) > r.get("weekly_hours_capacity", 40)
    return resp(200, {"data": rows, "success": True})


def get_person(person_id: str) -> dict:
    """GET /api/people/{id} — get person with allocation summary."""
    conn = get_db()
    with conn.cursor() as cur:
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
            return resp(404, {"error": "Person not found", "success": False})
        person = row_to_dict(cur, row)
    person["is_overallocated"] = person["allocated_hours_per_week"] > person["weekly_hours_capacity"]
    return resp(200, {"data": person, "success": True})


def get_allocation(person_id: str) -> dict:
    """GET /api/people/{id}/allocation — detailed allocation breakdown."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM people WHERE id = %s AND is_deleted = FALSE", (person_id,))
        row = cur.fetchone()
        if not row:
            return resp(404, {"error": "Person not found", "success": False})
        person = row_to_dict(cur, row)
        cur.execute(
            """
            SELECT a.*, pr.title AS project_title, pr.status AS project_status
            FROM assignments a
            JOIN projects pr ON pr.id = a.project_id
            WHERE a.person_id = %s AND a.is_deleted = FALSE
            ORDER BY pr.title
            """,
            (person_id,),
        )
        assignments = rows_to_dicts(cur)
    total = sum(a.get("hours_per_week", 0) for a in assignments)
    return resp(200, {"data": {
        **person,
        "allocated_hours_per_week": total,
        "is_overallocated": total > person["weekly_hours_capacity"],
        "assignments": assignments,
    }, "success": True})


def create_person(event: dict, user: dict) -> dict:
    """POST /api/people — create a new person."""
    if user.get("role") not in ("admin", "manager"):
        return resp(403, {"error": "Insufficient permissions", "success": False})
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return resp(400, {"error": "Invalid JSON body", "success": False})
    if not body.get("name", "").strip():
        return resp(400, {"error": "name is required", "success": False})
    if not body.get("email", "").strip():
        return resp(400, {"error": "email is required", "success": False})
    body["email"] = body["email"].lower().strip()
    body = filter_fields("people", body)
    err = _validate_person(body)
    if err:
        return resp(400, {"error": err, "success": False})
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM people WHERE email = %s AND is_deleted = FALSE", (body["email"],))
        if cur.fetchone():
            return resp(409, {"error": f"Person with email {body['email']} already exists", "success": False})
    cols = list(body.keys())
    vals = list(body.values())
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO people ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(vals))}) RETURNING *",
            vals,
        )
        row = cur.fetchone()
        conn.commit()
        return resp(201, {"data": row_to_dict(cur, row), "success": True})


def update_person(event: dict, person_id: str, user: dict) -> dict:
    """PUT /api/people/{id} — update a person."""
    if user.get("role") not in ("admin", "manager"):
        return resp(403, {"error": "Insufficient permissions", "success": False})
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return resp(400, {"error": "Invalid JSON body", "success": False})
    body = filter_fields("people", body)
    err = _validate_person(body)
    if err:
        return resp(400, {"error": err, "success": False})
    if not body:
        return resp(400, {"error": "No valid fields to update", "success": False})
    set_clause = ", ".join([f"{k} = %s" for k in body.keys()])
    vals = list(body.values()) + [person_id]
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE people SET {set_clause}, updated_at = NOW() WHERE id = %s AND is_deleted = FALSE RETURNING *",
            vals,
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            return resp(404, {"error": "Person not found", "success": False})
        return resp(200, {"data": row_to_dict(cur, row), "success": True})


def delete_person(person_id: str, user: dict) -> dict:
    """DELETE /api/people/{id} — soft delete a person."""
    if user.get("role") != "admin":
        return resp(403, {"error": "Admin role required", "success": False})
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE people SET is_deleted = TRUE, updated_at = NOW() WHERE id = %s AND is_deleted = FALSE",
            (person_id,),
        )
        conn.commit()
        if cur.rowcount == 0:
            return resp(404, {"error": "Person not found", "success": False})
    return resp(204, {})


def handler(event=None, context=None):
    if event is None:
        event = {}
    method = (event.get("requestContext") or {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "")

    if method == "OPTIONS":
        return resp(204, {})

    user = get_user(event)
    if not user:
        return resp(401, {"error": "Authentication required", "success": False})

    person_id = extract_id(path)
    sub_path = path.split("/")[-1] if path else ""

    try:
        if method == "GET" and person_id and sub_path == "allocation":
            return get_allocation(person_id)
        if method == "GET" and not person_id:
            return list_people(event)
        if method == "GET" and person_id:
            return get_person(person_id)
        if method == "POST":
            return create_person(event, user)
        if method == "PUT" and person_id:
            return update_person(event, person_id, user)
        if method == "DELETE" and person_id:
            return delete_person(person_id, user)
        return resp(405, {"error": "Method not allowed", "success": False})
    except Exception as exc:
        logger.error("Unhandled error: %s", exc, exc_info=True)
        return resp(500, {"error": "Internal server error", "success": False})


if __name__ == "__main__":
    print(handler({"requestContext": {"http": {"method": "GET"}}, "rawPath": "/api/people"}))

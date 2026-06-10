"""Projects Lambda — CRUD for the projects entity."""

import json
import logging

from shared import (
    get_db, resp, get_user, extract_id, rows_to_dicts, row_to_dict,
    calculate_health, filter_fields, get_scoped_project_ids,
    VALID_STATUSES, VALID_HEALTH,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_VALID_PROJECT_STATUSES = VALID_STATUSES.get("projects", set())


def _with_health(row: dict) -> dict:
    """Recomputes health + injects health_reason so display reflects current rules."""
    color, reason = calculate_health(row)
    row["health"] = color
    row["health_reason"] = reason
    return row


def _validate_project(body: dict) -> str | None:
    """Returns an error string if the body is invalid, else None."""
    status = body.get("status")
    if status is not None and status not in _VALID_PROJECT_STATUSES:
        return f"status must be one of: {sorted(_VALID_PROJECT_STATUSES)}"
    health = body.get("health")
    if health is not None and health not in VALID_HEALTH:
        return f"health must be one of: {sorted(VALID_HEALTH)}"
    for money_field in ("budget_planned", "budget_consumed"):
        val = body.get(money_field)
        if val is not None:
            try:
                if float(val) < 0:
                    return f"{money_field} must not be negative"
            except (TypeError, ValueError):
                return f"{money_field} must be a number"
    for date_field in ("start_date", "end_date"):
        val = body.get(date_field)
        if val is not None:
            try:
                from datetime import date
                date.fromisoformat(str(val)[:10])
            except ValueError:
                return f"{date_field} must be a valid ISO date (YYYY-MM-DD)"
    return None


def list_projects(event: dict) -> dict:
    """GET /api/projects — list all projects with optional filters."""
    params = event.get("queryStringParameters") or {}
    conn = get_db()
    scope_ids = get_scoped_project_ids(conn, get_user(event))
    conditions = ["is_deleted = FALSE"]
    vals: list = []
    if scope_ids is not None:
        if not scope_ids:
            return resp(200, {"data": [], "success": True})
        conditions.append("id = ANY(%s)")
        vals.append(scope_ids)
    if params.get("status"):
        if params["status"] not in _VALID_PROJECT_STATUSES:
            return resp(400, {"error": f"status must be one of: {sorted(_VALID_PROJECT_STATUSES)}", "success": False})
        conditions.append("status = %s")
        vals.append(params["status"])
    if params.get("health"):
        if params["health"] not in VALID_HEALTH:
            return resp(400, {"error": f"health must be one of: {sorted(VALID_HEALTH)}", "success": False})
        conditions.append("health = %s")
        vals.append(params["health"])
    if params.get("search"):
        conditions.append("LOWER(title) LIKE %s")
        vals.append(f"%{params['search'].lower()}%")
    try:
        limit = min(int(params.get("limit", 100)), 500)
        offset = int(params.get("offset", 0))
    except (TypeError, ValueError):
        return resp(400, {"error": "limit and offset must be integers", "success": False})
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM projects WHERE {' AND '.join(conditions)} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            vals + [limit, offset],
        )
        return resp(200, {"data": [_with_health(r) for r in rows_to_dicts(cur)], "success": True})


def get_project(event: dict, project_id: str) -> dict:
    """GET /api/projects/{id} — get a single project."""
    conn = get_db()
    scope_ids = get_scoped_project_ids(conn, get_user(event))
    if scope_ids is not None and project_id not in scope_ids:
        return resp(404, {"error": "Project not found", "success": False})
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM projects WHERE id = %s AND is_deleted = FALSE", (project_id,))
        row = cur.fetchone()
        if not row:
            return resp(404, {"error": "Project not found", "success": False})
        return resp(200, {"data": _with_health(row_to_dict(cur, row)), "success": True})


def create_project(event: dict, user: dict) -> dict:
    """POST /api/projects — create a new project."""
    if user.get("role") not in ("admin", "manager"):
        return resp(403, {"error": "Insufficient permissions", "success": False})
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return resp(400, {"error": "Invalid JSON body", "success": False})
    if not body.get("title", "").strip():
        return resp(400, {"error": "title is required", "success": False})
    body = filter_fields("projects", body)
    err = _validate_project(body)
    if err:
        return resp(400, {"error": err, "success": False})
    body["health"], _ = calculate_health(body)
    body["created_by"] = user.get("sub")
    cols = list(body.keys())
    vals = list(body.values())
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO projects ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(vals))}) RETURNING *",
            vals,
        )
        row = cur.fetchone()
        conn.commit()
        return resp(201, {"data": _with_health(row_to_dict(cur, row)), "success": True})


def update_project(event: dict, project_id: str, user: dict) -> dict:
    """PUT /api/projects/{id} — update a project."""
    if user.get("role") not in ("admin", "manager"):
        return resp(403, {"error": "Insufficient permissions", "success": False})
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return resp(400, {"error": "Invalid JSON body", "success": False})
    body = filter_fields("projects", body)
    err = _validate_project(body)
    if err:
        return resp(400, {"error": err, "success": False})
    if not body:
        return resp(400, {"error": "No valid fields to update", "success": False})
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM projects WHERE id = %s AND is_deleted = FALSE", (project_id,))
        existing_row = cur.fetchone()
        if not existing_row:
            return resp(404, {"error": "Project not found", "success": False})
        existing = row_to_dict(cur, existing_row)
    merged = {**existing, **body}
    body["health"], _ = calculate_health(merged)
    set_clause = ", ".join([f"{k} = %s" for k in body.keys()])
    vals = list(body.values()) + [project_id]
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE projects SET {set_clause}, updated_at = NOW() WHERE id = %s AND is_deleted = FALSE RETURNING *",
            vals,
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            return resp(404, {"error": "Project not found", "success": False})
        return resp(200, {"data": _with_health(row_to_dict(cur, row)), "success": True})


def delete_project(project_id: str, user: dict) -> dict:
    """DELETE /api/projects/{id} — soft delete a project."""
    if user.get("role") != "admin":
        return resp(403, {"error": "Admin role required", "success": False})
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE projects SET is_deleted = TRUE, updated_at = NOW() WHERE id = %s AND is_deleted = FALSE",
            (project_id,),
        )
        conn.commit()
        if cur.rowcount == 0:
            return resp(404, {"error": "Project not found", "success": False})
    return resp(204, {})


def handler(event=None, context=None):
    """Main Lambda entry point."""
    if event is None:
        event = {}
    method = (event.get("requestContext") or {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "")

    if method == "OPTIONS":
        return resp(204, {})

    user = get_user(event)
    if not user:
        return resp(401, {"error": "Authentication required", "success": False})

    project_id = extract_id(path)

    try:
        if method == "GET" and not project_id:
            return list_projects(event)
        if method == "GET" and project_id:
            return get_project(event, project_id)
        if method == "POST":
            return create_project(event, user)
        if method == "PUT" and project_id:
            return update_project(event, project_id, user)
        if method == "DELETE" and project_id:
            return delete_project(project_id, user)
        return resp(405, {"error": "Method not allowed", "success": False})
    except Exception as exc:
        logger.error("Unhandled error: %s", exc, exc_info=True)
        return resp(500, {"error": f"{type(exc).__name__}: {exc}", "success": False})


if __name__ == "__main__":
    print(handler({"requestContext": {"http": {"method": "GET"}}, "rawPath": "/api/projects"}))

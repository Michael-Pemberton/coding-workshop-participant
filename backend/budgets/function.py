"""Budgets Lambda — CRUD for project budget items."""

import json
import logging

from shared import (
    get_db, resp, get_user, extract_id, rows_to_dicts, row_to_dict, init_db,
    filter_fields, VALID_BUDGET_CATEGORIES,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

try:
    init_db()
except Exception as exc:
    logger.error("DB init failed: %s", exc)


def _validate_budget(body: dict) -> str | None:
    """Returns an error string if the body is invalid, else None."""
    for money_field in ("amount_planned", "amount_consumed"):
        val = body.get(money_field)
        if val is not None:
            try:
                f = float(val)
                if f < 0:
                    return f"{money_field} must not be negative"
            except (TypeError, ValueError):
                return f"{money_field} must be a number"
    category = body.get("category")
    if category is not None and category not in VALID_BUDGET_CATEGORIES:
        return f"category must be one of: {sorted(VALID_BUDGET_CATEGORIES)}"
    return None


def sync_project_budget(conn, project_id: str):
    """Recalculates project.budget_consumed from sum of active budget items."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE projects SET "
            "budget_consumed = (SELECT COALESCE(SUM(amount_consumed),0) FROM budget_items WHERE project_id = %s AND is_deleted = FALSE), "
            "updated_at = NOW() WHERE id = %s",
            (project_id, project_id),
        )
    conn.commit()


def handler(event=None, context=None):
    """Routes budget CRUD requests."""
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
            conditions = ["is_deleted = FALSE"]
            vals: list = []
            if params.get("project_id"):
                conditions.append("project_id = %s")
                vals.append(params["project_id"])
            try:
                limit = min(int(params.get("limit", 100)), 500)
                offset = int(params.get("offset", 0))
            except (TypeError, ValueError):
                return resp(400, {"error": "limit and offset must be integers", "success": False})
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM budget_items WHERE {' AND '.join(conditions)} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    vals + [limit, offset],
                )
                return resp(200, {"data": rows_to_dicts(cur), "success": True})

        if method == "GET" and item_id:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM budget_items WHERE id = %s AND is_deleted = FALSE", (item_id,))
                row = cur.fetchone()
                if not row:
                    return resp(404, {"error": "Budget item not found", "success": False})
                return resp(200, {"data": row_to_dict(cur, row), "success": True})

        if method == "POST":
            if user.get("role") not in ("admin", "manager"):
                return resp(403, {"error": "Insufficient permissions", "success": False})
            body = json.loads(event.get("body") or "{}")
            if not body.get("project_id"):
                return resp(400, {"error": "project_id is required", "success": False})
            body = filter_fields("budget_items", body)
            err = _validate_budget(body)
            if err:
                return resp(400, {"error": err, "success": False})
            cols = list(body.keys())
            vals2 = list(body.values())
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO budget_items ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(vals2))}) RETURNING *",
                    vals2,
                )
                row = cur.fetchone()
                conn.commit()
                result = row_to_dict(cur, row)
            sync_project_budget(conn, body["project_id"])
            return resp(201, {"data": result, "success": True})

        if method == "PUT" and item_id:
            if user.get("role") not in ("admin", "manager"):
                return resp(403, {"error": "Insufficient permissions", "success": False})
            body = json.loads(event.get("body") or "{}")
            body = filter_fields("budget_items", body)
            err = _validate_budget(body)
            if err:
                return resp(400, {"error": err, "success": False})
            if not body:
                return resp(400, {"error": "No valid fields to update", "success": False})
            set_clause = ", ".join([f"{k} = %s" for k in body.keys()])
            vals3 = list(body.values()) + [item_id]
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE budget_items SET {set_clause}, updated_at = NOW() WHERE id = %s AND is_deleted = FALSE RETURNING *",
                    vals3,
                )
                row = cur.fetchone()
                conn.commit()
                if not row:
                    return resp(404, {"error": "Budget item not found", "success": False})
                result = row_to_dict(cur, row)
            sync_project_budget(conn, result["project_id"])
            return resp(200, {"data": result, "success": True})

        if method == "DELETE" and item_id:
            if user.get("role") not in ("admin", "manager"):
                return resp(403, {"error": "Insufficient permissions", "success": False})
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT project_id FROM budget_items WHERE id = %s AND is_deleted = FALSE",
                    (item_id,),
                )
                row = cur.fetchone()
                if not row:
                    return resp(404, {"error": "Budget item not found", "success": False})
                project_id = row[0]
                cur.execute(
                    "UPDATE budget_items SET is_deleted = TRUE, updated_at = NOW() WHERE id = %s",
                    (item_id,),
                )
                conn.commit()
            sync_project_budget(conn, str(project_id))
            return resp(204, {})

        return resp(405, {"error": "Method not allowed", "success": False})
    except Exception as exc:
        logger.error("Error: %s", exc, exc_info=True)
        return resp(500, {"error": "Internal server error", "success": False})


if __name__ == "__main__":
    print(handler({"requestContext": {"http": {"method": "GET"}}, "rawPath": "/api/budgets"}))

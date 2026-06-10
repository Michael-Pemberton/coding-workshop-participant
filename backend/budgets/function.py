"""Budgets Lambda — CRUD for project budget items."""

import json
import logging

from shared import (
    get_db, resp, get_user, extract_id, rows_to_dicts, row_to_dict,
    filter_fields, VALID_BUDGET_CATEGORIES,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


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
    """Raises project.budget_consumed if items sum exceeds it. Never lowers — preserves unallocated headroom."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE projects SET "
            "budget_consumed = GREATEST(COALESCE(budget_consumed,0), "
            "(SELECT COALESCE(SUM(amount_consumed),0) FROM budget_items WHERE project_id = %s AND is_deleted = FALSE)), "
            "updated_at = NOW() WHERE id = %s",
            (project_id, project_id),
        )
    conn.commit()


def _project_weeks(conn, project_id: str) -> float:
    """Returns the project's duration in weeks (end - start)/7. 0 if dates missing."""
    with conn.cursor() as cur:
        cur.execute("SELECT start_date, end_date FROM projects WHERE id = %s AND is_deleted = FALSE", (project_id,))
        row = cur.fetchone()
    if not row or not row[0] or not row[1]:
        return 0.0
    days = (row[1] - row[0]).days
    return max(0.0, days / 7.0)


def list_staff_budget(conn, project_id: str) -> dict:
    """Computes per-person planned/actual for a project from assignments × hourly_pay × weeks,
    layered with any per-row overrides from staff_budget_overrides."""
    weeks = _project_weeks(conn, project_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.person_id, p.name, p.hourly_pay, a.role_on_project, a.hours_per_week,
                   o.amount_planned, o.amount_consumed
            FROM assignments a
            JOIN people p ON p.id = a.person_id AND p.is_deleted = FALSE
            LEFT JOIN staff_budget_overrides o
              ON o.project_id = a.project_id AND o.person_id = a.person_id AND o.is_deleted = FALSE
            WHERE a.project_id = %s AND a.is_deleted = FALSE
            ORDER BY p.name
            """,
            (project_id,),
        )
        rows = cur.fetchall()
    items = []
    for person_id, name, hourly_pay, role, hours, ov_planned, ov_consumed in rows:
        rate = float(hourly_pay or 0)
        hpw = float(hours or 0)
        planned_auto = round(rate * hpw * weeks, 2)
        planned_eff = float(ov_planned) if ov_planned is not None else planned_auto
        consumed_eff = float(ov_consumed) if ov_consumed is not None else 0.0
        items.append({
            "person_id": str(person_id),
            "name": name,
            "role_on_project": role,
            "hours_per_week": hpw,
            "hourly_pay": rate,
            "weeks": round(weeks, 2),
            "amount_planned_auto": planned_auto,
            "amount_planned": planned_eff,
            "amount_consumed": consumed_eff,
            "planned_overridden": ov_planned is not None,
            "consumed_overridden": ov_consumed is not None,
        })
    return {
        "items": items,
        "weeks": round(weeks, 2),
        "total_planned": round(sum(i["amount_planned"] for i in items), 2),
        "total_consumed": round(sum(i["amount_consumed"] for i in items), 2),
    }


def upsert_staff_override(conn, body: dict) -> dict | None:
    """Upserts a per-person override. Null fields clear the override (fall back to auto)."""
    project_id = body.get("project_id")
    person_id = body.get("person_id")
    if not project_id or not person_id:
        return {"error": "project_id and person_id are required"}
    for k in ("amount_planned", "amount_consumed"):
        v = body.get(k)
        if v is not None and v != "":
            try:
                if float(v) < 0:
                    return {"error": f"{k} must not be negative"}
            except (TypeError, ValueError):
                return {"error": f"{k} must be a number"}
    ap = body.get("amount_planned")
    ac = body.get("amount_consumed")
    ap = None if ap == "" or ap is None else float(ap)
    ac = None if ac == "" or ac is None else float(ac)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO staff_budget_overrides (project_id, person_id, amount_planned, amount_consumed)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (project_id, person_id) DO UPDATE
            SET amount_planned = EXCLUDED.amount_planned,
                amount_consumed = EXCLUDED.amount_consumed,
                is_deleted = FALSE,
                updated_at = NOW()
            """,
            (project_id, person_id, ap, ac),
        )
    conn.commit()
    return None


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

    # Sub-routes for the computed/override staff budget.
    if path.endswith("/staff"):
        if method != "GET":
            return resp(405, {"error": "Method not allowed", "success": False})
        pid = params.get("project_id")
        if not pid:
            return resp(400, {"error": "project_id is required", "success": False})
        try:
            return resp(200, {"data": list_staff_budget(conn, pid), "success": True})
        except Exception as exc:
            logger.error("staff list error: %s", exc, exc_info=True)
            return resp(500, {"error": f"{type(exc).__name__}: {exc}", "success": False})

    if path.endswith("/staff/override"):
        if method != "PUT":
            return resp(405, {"error": "Method not allowed", "success": False})
        if user.get("role") not in ("admin", "manager"):
            return resp(403, {"error": "Insufficient permissions", "success": False})
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return resp(400, {"error": "Invalid JSON body", "success": False})
        err = upsert_staff_override(conn, body)
        if err:
            return resp(400, {"error": err["error"], "success": False})
        return resp(200, {"data": list_staff_budget(conn, body["project_id"]), "success": True})

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
        return resp(500, {"error": f"{type(exc).__name__}: {exc}", "success": False})


if __name__ == "__main__":
    print(handler({"requestContext": {"http": {"method": "GET"}}, "rawPath": "/api/budgets"}))

"""Integration tests — hit a real Postgres instance.

Each test runs in a transaction that is rolled back at the end, so no state
leaks between tests or into your dev DB. Skipped automatically if Postgres is
not reachable on localhost:5432.

Run with:
    cd backend && IS_LOCAL=true JWT_SECRET=test-secret python -m pytest tests/test_integration.py -v
"""

import json
import uuid

import pytest

from tests.conftest import integration_handler, make_event


# ---------- helpers ----------------------------------------------------------

def _body(result):
    return json.loads(result["body"])


def _insert_project(conn, title="Integ Project", **extra) -> str:
    """Inserts a project directly and returns its UUID."""
    cols = ["title"]
    vals = [title]
    for k, v in extra.items():
        cols.append(k)
        vals.append(v)
    placeholders = ", ".join(["%s"] * len(vals))
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO projects ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id",
            vals,
        )
        return str(cur.fetchone()[0])


def _insert_person(conn, **extra) -> str:
    name = extra.pop("name", "Integ Person")
    email = extra.pop("email", f"integ-{uuid.uuid4()}@example.com")
    cols = ["name", "email"]
    vals = [name, email]
    for k, v in extra.items():
        cols.append(k)
        vals.append(v)
    placeholders = ", ".join(["%s"] * len(vals))
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO people ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id",
            vals,
        )
        return str(cur.fetchone()[0])


# ---------- projects ---------------------------------------------------------

def test_int_projects_create_list_get_update_delete(mocker, integration_db):
    h = integration_handler("projects", mocker, integration_db)

    # CREATE
    create = h.handler(make_event("POST", "/api/projects", body={
        "title": "Integ Alpha",
        "description": "from integration test",
        "status": "active",
        "budget_planned": 1000,
    }))
    assert create["statusCode"] == 201, _body(create)
    pid = _body(create)["data"]["id"]

    # GET single
    got = h.handler(make_event("GET", f"/api/projects/{pid}"))
    assert got["statusCode"] == 200
    assert _body(got)["data"]["title"] == "Integ Alpha"

    # LIST contains it
    listed = h.handler(make_event("GET", "/api/projects"))
    assert listed["statusCode"] == 200
    titles = [p["title"] for p in _body(listed)["data"]]
    assert "Integ Alpha" in titles

    # UPDATE
    updated = h.handler(make_event("PUT", f"/api/projects/{pid}", body={"title": "Integ Alpha v2"}))
    assert updated["statusCode"] == 200
    assert _body(updated)["data"]["title"] == "Integ Alpha v2"

    # DELETE (soft)
    deleted = h.handler(make_event("DELETE", f"/api/projects/{pid}"))
    assert deleted["statusCode"] in (200, 204)

    # GET after delete → 404
    gone = h.handler(make_event("GET", f"/api/projects/{pid}"))
    assert gone["statusCode"] == 404


# ---------- people -----------------------------------------------------------

def test_int_people_crud(mocker, integration_db):
    h = integration_handler("people", mocker, integration_db)
    unique_email = f"integ-{uuid.uuid4()}@example.com"

    create = h.handler(make_event("POST", "/api/people", body={
        "name": "Integ Tester",
        "email": unique_email,
        "weekly_hours_capacity": 30,
        "hourly_pay": 75,
    }))
    assert create["statusCode"] == 201, _body(create)
    person_id = _body(create)["data"]["id"]

    got = h.handler(make_event("GET", f"/api/people/{person_id}"))
    assert got["statusCode"] == 200
    assert _body(got)["data"]["email"] == unique_email


def test_int_people_duplicate_email_returns_error(mocker, integration_db):
    h = integration_handler("people", mocker, integration_db)
    email = f"dup-{uuid.uuid4()}@example.com"

    first = h.handler(make_event("POST", "/api/people", body={"name": "A", "email": email}))
    assert first["statusCode"] == 201

    second = h.handler(make_event("POST", "/api/people", body={"name": "B", "email": email}))
    assert second["statusCode"] in (400, 409, 500)  # depends on handler's mapping


# ---------- assignments ------------------------------------------------------

def test_int_assignment_overallocation_against_real_db(mocker, integration_db):
    h = integration_handler("assignments", mocker, integration_db)
    project_id = _insert_project(integration_db, title="Integ Assign Proj")
    person_id = _insert_person(integration_db, weekly_hours_capacity=40)

    result = h.handler(make_event("POST", "/api/assignments", body={
        "person_id": person_id,
        "project_id": project_id,
        "hours_per_week": 50,
        "role_on_project": "lead",
    }))
    assert result["statusCode"] == 201, _body(result)
    data = _body(result)["data"]
    assert data["overallocation_warning"] is True
    assert data["total_allocated_hours"] == 50
    assert data["capacity"] == 40


def test_int_assignment_duplicate_returns_400(mocker, integration_db):
    h = integration_handler("assignments", mocker, integration_db)
    project_id = _insert_project(integration_db, title="Dup Assign Proj")
    person_id = _insert_person(integration_db)

    first = h.handler(make_event("POST", "/api/assignments", body={
        "person_id": person_id, "project_id": project_id, "hours_per_week": 10,
    }))
    assert first["statusCode"] == 201

    second = h.handler(make_event("POST", "/api/assignments", body={
        "person_id": person_id, "project_id": project_id, "hours_per_week": 10,
    }))
    assert second["statusCode"] == 400
    assert "already assigned" in _body(second)["error"].lower()


# ---------- deliverables -----------------------------------------------------

def test_int_deliverable_cycle_rejected(mocker, integration_db):
    h = integration_handler("deliverables", mocker, integration_db)
    project_id = _insert_project(integration_db, title="Cycle Proj")

    a = h.handler(make_event("POST", "/api/deliverables", body={
        "title": "A", "project_id": project_id,
    }))
    assert a["statusCode"] == 201
    a_id = _body(a)["data"]["id"]

    b = h.handler(make_event("POST", "/api/deliverables", body={
        "title": "B", "project_id": project_id, "depends_on_id": a_id,
    }))
    assert b["statusCode"] == 201
    b_id = _body(b)["data"]["id"]

    # Now point A → B, which would create cycle A → B → A.
    cyclic = h.handler(make_event("PUT", f"/api/deliverables/{a_id}", body={
        "depends_on_id": b_id,
    }))
    assert cyclic["statusCode"] == 400
    assert "cycle" in _body(cyclic)["error"].lower()


def test_int_deliverable_self_reference_rejected(mocker, integration_db):
    h = integration_handler("deliverables", mocker, integration_db)
    project_id = _insert_project(integration_db, title="Self Ref Proj")
    a = h.handler(make_event("POST", "/api/deliverables", body={
        "title": "A", "project_id": project_id,
    }))
    a_id = _body(a)["data"]["id"]
    self_ref = h.handler(make_event("PUT", f"/api/deliverables/{a_id}", body={
        "depends_on_id": a_id,
    }))
    assert self_ref["statusCode"] == 400


# ---------- budgets ----------------------------------------------------------

def test_int_budget_sync_raises_project_consumed(mocker, integration_db):
    h = integration_handler("budgets", mocker, integration_db)
    project_id = _insert_project(integration_db, title="Sync Proj", budget_planned=1000, budget_consumed=0)

    create = h.handler(make_event("POST", "/api/budgets", body={
        "project_id": project_id,
        "category": "tooling",
        "amount_planned": 200,
        "amount_consumed": 150,
    }))
    assert create["statusCode"] == 201, _body(create)

    # sync_project_budget should have raised projects.budget_consumed to 150.
    with integration_db.cursor() as cur:
        cur.execute("SELECT budget_consumed FROM projects WHERE id = %s", (project_id,))
        consumed = float(cur.fetchone()[0])
    assert consumed >= 150


def test_int_budget_sync_never_lowers_existing_consumed(mocker, integration_db):
    h = integration_handler("budgets", mocker, integration_db)
    # Project already has consumed=500 (e.g. from manual entry).
    project_id = _insert_project(integration_db, title="No Lower Proj",
                                  budget_planned=1000, budget_consumed=500)

    create = h.handler(make_event("POST", "/api/budgets", body={
        "project_id": project_id,
        "category": "travel",
        "amount_planned": 100,
        "amount_consumed": 50,  # less than existing 500
    }))
    assert create["statusCode"] == 201

    with integration_db.cursor() as cur:
        cur.execute("SELECT budget_consumed FROM projects WHERE id = %s", (project_id,))
        consumed = float(cur.fetchone()[0])
    assert consumed == 500  # unchanged — GREATEST() preserved the higher value


# ---------- staff budget endpoints ------------------------------------------

def test_int_staff_budget_list_computes_auto_amounts(mocker, integration_db):
    h = integration_handler("budgets", mocker, integration_db)
    project_id = _insert_project(
        integration_db, title="Staff Proj",
        start_date="2025-01-01", end_date="2025-01-15",  # 2 weeks
    )
    person_id = _insert_person(integration_db, hourly_pay=100)
    # Attach the person to the project.
    with integration_db.cursor() as cur:
        cur.execute(
            "INSERT INTO assignments (person_id, project_id, role_on_project, hours_per_week) "
            "VALUES (%s, %s, %s, %s)",
            (person_id, project_id, "dev", 10),
        )

    result = h.handler(make_event(
        "GET", "/api/budgets/staff", params={"project_id": project_id},
    ))
    assert result["statusCode"] == 200, _body(result)
    data = _body(result)["data"]
    assert len(data["items"]) == 1
    item = data["items"][0]
    # 100/hr × 10 hrs/wk × 2 wks = 2000
    assert item["amount_planned_auto"] == 2000.0
    assert item["amount_planned"] == 2000.0
    assert item["consumed_overridden"] is False


def test_int_staff_budget_list_requires_project_id(mocker, integration_db):
    h = integration_handler("budgets", mocker, integration_db)
    result = h.handler(make_event("GET", "/api/budgets/staff"))
    assert result["statusCode"] == 400


def test_int_staff_override_replaces_auto_amount(mocker, integration_db):
    h = integration_handler("budgets", mocker, integration_db)
    project_id = _insert_project(
        integration_db, title="Override Proj",
        start_date="2025-01-01", end_date="2025-01-08",
    )
    person_id = _insert_person(integration_db, hourly_pay=50)
    with integration_db.cursor() as cur:
        cur.execute(
            "INSERT INTO assignments (person_id, project_id, hours_per_week) VALUES (%s, %s, %s)",
            (person_id, project_id, 20),
        )

    override = h.handler(make_event("PUT", "/api/budgets/staff/override", body={
        "project_id": project_id,
        "person_id": person_id,
        "amount_planned": 9999,
        "amount_consumed": 1234,
    }))
    assert override["statusCode"] == 200, _body(override)
    items = _body(override)["data"]["items"]
    assert len(items) == 1
    assert items[0]["amount_planned"] == 9999.0
    assert items[0]["amount_consumed"] == 1234.0
    assert items[0]["planned_overridden"] is True


def test_int_staff_override_negative_amount_rejected(mocker, integration_db):
    h = integration_handler("budgets", mocker, integration_db)
    project_id = _insert_project(integration_db, title="Neg Override")
    person_id = _insert_person(integration_db)
    result = h.handler(make_event("PUT", "/api/budgets/staff/override", body={
        "project_id": project_id,
        "person_id": person_id,
        "amount_planned": -5,
    }))
    assert result["statusCode"] == 400


# ---------- PUT / DELETE coverage -------------------------------------------

def test_int_people_update_and_delete(mocker, integration_db):
    h = integration_handler("people", mocker, integration_db)
    person_id = _insert_person(integration_db, name="Before")

    updated = h.handler(make_event("PUT", f"/api/people/{person_id}", body={
        "name": "After", "weekly_hours_capacity": 25,
    }))
    assert updated["statusCode"] == 200
    assert _body(updated)["data"]["name"] == "After"

    deleted = h.handler(make_event("DELETE", f"/api/people/{person_id}"))
    assert deleted["statusCode"] in (200, 204)

    after = h.handler(make_event("GET", f"/api/people/{person_id}"))
    assert after["statusCode"] == 404


def test_int_assignment_update_and_delete(mocker, integration_db):
    h = integration_handler("assignments", mocker, integration_db)
    pid = _insert_project(integration_db, title="A/D Proj")
    person_id = _insert_person(integration_db)
    create = h.handler(make_event("POST", "/api/assignments", body={
        "person_id": person_id, "project_id": pid, "hours_per_week": 10,
    }))
    assert create["statusCode"] == 201
    aid = _body(create)["data"]["id"]

    updated = h.handler(make_event("PUT", f"/api/assignments/{aid}", body={"hours_per_week": 15}))
    assert updated["statusCode"] == 200
    assert _body(updated)["data"]["hours_per_week"] == 15

    deleted = h.handler(make_event("DELETE", f"/api/assignments/{aid}"))
    assert deleted["statusCode"] in (200, 204)


def test_int_deliverable_update_and_delete(mocker, integration_db):
    h = integration_handler("deliverables", mocker, integration_db)
    pid = _insert_project(integration_db, title="Deliv U/D Proj")
    create = h.handler(make_event("POST", "/api/deliverables", body={
        "title": "v1", "project_id": pid,
    }))
    did = _body(create)["data"]["id"]

    updated = h.handler(make_event("PUT", f"/api/deliverables/{did}", body={
        "title": "v2", "due_date": "2030-01-01",
    }))
    assert updated["statusCode"] == 200
    assert _body(updated)["data"]["title"] == "v2"

    deleted = h.handler(make_event("DELETE", f"/api/deliverables/{did}"))
    assert deleted["statusCode"] in (200, 204)


def test_int_budget_item_update_and_delete(mocker, integration_db):
    h = integration_handler("budgets", mocker, integration_db)
    pid = _insert_project(integration_db, title="Budget U/D Proj")
    create = h.handler(make_event("POST", "/api/budgets", body={
        "project_id": pid, "category": "tooling", "amount_planned": 100,
    }))
    bid = _body(create)["data"]["id"]

    updated = h.handler(make_event("PUT", f"/api/budgets/{bid}", body={"amount_consumed": 75}))
    assert updated["statusCode"] == 200

    deleted = h.handler(make_event("DELETE", f"/api/budgets/{bid}"))
    assert deleted["statusCode"] in (200, 204)


# ---------- auth flows -------------------------------------------------------

def test_int_password_login_success_then_get_me(mocker, integration_db):
    h = integration_handler("auth", mocker, integration_db)
    from shared import hash_password
    username = f"user-{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    with integration_db.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, name, email, password_hash, user_role) "
            "VALUES (%s, %s, %s, %s, %s)",
            (username, "Test User", email, hash_password("password123"), "manager"),
        )

    login = h.handler(make_event("POST", "/api/auth/login", body={
        "username": username, "password": "password123",
    }))
    assert login["statusCode"] == 200, _body(login)
    body = _body(login)["data"]
    assert "token" in body
    assert body["user"]["email"] == email
    assert "password_hash" not in body["user"]


def test_int_password_login_wrong_password_records_failure(mocker, integration_db):
    h = integration_handler("auth", mocker, integration_db)
    from shared import hash_password
    username = f"user-{uuid.uuid4().hex[:8]}"
    h.handler  # ensure module loaded
    h._failed_attempts.clear()
    with integration_db.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, name, email, password_hash) VALUES (%s, %s, %s, %s)",
            (username, "X", f"{username}@x.com", hash_password("rightpassword")),
        )

    result = h.handler(make_event("POST", "/api/auth/login", body={
        "username": username, "password": "wrongpassword",
    }))
    assert result["statusCode"] == 401
    assert h._failed_attempts.get(username, (0,))[0] == 1


def test_int_password_login_unknown_user_returns_401(mocker, integration_db):
    h = integration_handler("auth", mocker, integration_db)
    h._failed_attempts.clear()
    result = h.handler(make_event("POST", "/api/auth/login", body={
        "username": f"ghost-{uuid.uuid4().hex[:8]}", "password": "anything",
    }))
    assert result["statusCode"] == 401


def test_int_create_and_update_user(mocker, integration_db):
    h = integration_handler("auth", mocker, integration_db)
    username = f"u-{uuid.uuid4().hex[:8]}"
    create = h.create_user({
        "username": username, "name": "New", "email": f"{username}@x.com",
        "password": "longpassword", "role": "contributor",
    })
    assert create["statusCode"] == 201, _body(create)
    user_id = _body(create)["data"]["id"]

    # Duplicate username/email → 409
    dup = h.create_user({
        "username": username, "name": "Dup", "email": f"{username}@x.com",
        "password": "longpassword", "role": "viewer",
    })
    assert dup["statusCode"] == 409

    updated = h.update_user(user_id, {"name": "Renamed", "role": "manager"})
    assert updated["statusCode"] == 200
    assert _body(updated)["data"]["name"] == "Renamed"
    assert _body(updated)["data"]["user_role"] == "manager"


def test_int_delete_user_deactivates(mocker, integration_db):
    h = integration_handler("auth", mocker, integration_db)
    from shared import hash_password
    username = f"u-{uuid.uuid4().hex[:8]}"
    with integration_db.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, name, email, password_hash) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (username, "X", f"{username}@x.com", hash_password("longenough")),
        )
        target_id = str(cur.fetchone()[0])

    deleted = h.delete_user(target_id, "different-admin-id")
    assert deleted["statusCode"] == 200

    with integration_db.cursor() as cur:
        cur.execute("SELECT is_active FROM users WHERE id = %s", (target_id,))
        assert cur.fetchone()[0] is False


def test_int_auth_handler_get_me(mocker, integration_db):
    h = integration_handler("auth", mocker, integration_db)
    email = f"me-{uuid.uuid4()}@x.com"
    with integration_db.cursor() as cur:
        cur.execute(
            "INSERT INTO users (name, email, user_role) VALUES (%s, %s, %s)",
            ("Me User", email, "manager"),
        )
    mocker.patch.object(h, "get_user_from_token",
                         return_value={"sub": "x", "email": email, "name": "Me User", "role": "manager"})
    mocker.patch.object(h, "IS_LOCAL", False)
    event = make_event("GET", "/api/auth/me")
    event["headers"] = {"Authorization": "Bearer x"}
    result = h.handler(event)
    assert result["statusCode"] == 200
    assert _body(result)["data"]["email"] == email
    assert "password_hash" not in _body(result)["data"]


def test_int_auth_handler_list_users_as_admin(mocker, integration_db):
    h = integration_handler("auth", mocker, integration_db)
    with integration_db.cursor() as cur:
        cur.execute(
            "INSERT INTO users (name, email) VALUES (%s, %s)",
            (f"L-{uuid.uuid4().hex[:6]}", f"l-{uuid.uuid4()}@x.com"),
        )
    mocker.patch.object(h, "get_user_from_token",
                         return_value={"sub": "a", "email": "a@x.com", "role": "admin"})
    mocker.patch.object(h, "IS_LOCAL", False)
    event = make_event("GET", "/api/auth/users")
    event["headers"] = {"Authorization": "Bearer x"}
    result = h.handler(event)
    assert result["statusCode"] == 200
    assert isinstance(_body(result)["data"], list)


def test_int_auth_handler_create_user_via_route(mocker, integration_db):
    h = integration_handler("auth", mocker, integration_db)
    mocker.patch.object(h, "get_user_from_token",
                         return_value={"sub": "a", "email": "a@x.com", "role": "admin"})
    mocker.patch.object(h, "IS_LOCAL", False)
    event = make_event("POST", "/api/auth/users", body={
        "username": f"u-{uuid.uuid4().hex[:8]}",
        "name": "Created",
        "email": f"c-{uuid.uuid4()}@x.com",
        "password": "longpassword",
        "role": "viewer",
    })
    event["headers"] = {"Authorization": "Bearer x"}
    result = h.handler(event)
    assert result["statusCode"] == 201


def test_int_auth_handler_update_role_via_route(mocker, integration_db):
    h = integration_handler("auth", mocker, integration_db)
    with integration_db.cursor() as cur:
        cur.execute(
            "INSERT INTO users (name, email, user_role) VALUES (%s, %s, %s) RETURNING id",
            ("RoleUser", f"r-{uuid.uuid4()}@x.com", "viewer"),
        )
        target_id = str(cur.fetchone()[0])
    mocker.patch.object(h, "get_user_from_token",
                         return_value={"sub": "a", "email": "a@x.com", "role": "admin"})
    mocker.patch.object(h, "IS_LOCAL", False)
    event = make_event("PUT", f"/api/auth/users/{target_id}/role", body={"role": "manager"})
    event["headers"] = {"Authorization": "Bearer x"}
    result = h.handler(event)
    assert result["statusCode"] == 200
    assert _body(result)["data"]["user_role"] == "manager"


def test_int_update_user_email_username_password_and_is_active(mocker, integration_db):
    h = integration_handler("auth", mocker, integration_db)
    from shared import hash_password, verify_password
    username = f"u-{uuid.uuid4().hex[:8]}"
    with integration_db.cursor() as cur:
        cur.execute(
            "INSERT INTO users (username, name, email, password_hash) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (username, "Orig", f"{username}@x.com", hash_password("origpassword")),
        )
        uid = str(cur.fetchone()[0])

    new_email = f"new-{uuid.uuid4()}@x.com"
    new_username = f"newu-{uuid.uuid4().hex[:6]}"
    result = h.update_user(uid, {
        "email": new_email,
        "username": new_username,
        "password": "brandnewpassword",
        "is_active": False,
    })
    assert result["statusCode"] == 200
    data = _body(result)["data"]
    assert data["email"] == new_email
    assert data["username"] == new_username
    assert data["is_active"] is False

    with integration_db.cursor() as cur:
        cur.execute("SELECT password_hash FROM users WHERE id = %s", (uid,))
        new_hash = cur.fetchone()[0]
    assert verify_password("brandnewpassword", new_hash)


def test_int_update_user_short_password_rejected(mocker, integration_db):
    h = integration_handler("auth", mocker, integration_db)
    result = h.update_user("any-id", {"password": "short"})
    assert result["statusCode"] == 400


def test_int_update_user_no_fields_rejected(mocker, integration_db):
    h = integration_handler("auth", mocker, integration_db)
    result = h.update_user("any-id", {})
    assert result["statusCode"] == 400


def test_int_update_user_not_found(mocker, integration_db):
    h = integration_handler("auth", mocker, integration_db)
    fake_id = "00000000-0000-0000-0000-000000000999"
    result = h.update_user(fake_id, {"name": "Whatever"})
    assert result["statusCode"] == 404


# ---------- PUT on non-existent IDs → 404 (each handler) --------------------

FAKE_UUID = "00000000-0000-0000-0000-0000000000ff"


def test_int_put_project_not_found(mocker, integration_db):
    h = integration_handler("projects", mocker, integration_db)
    result = h.handler(make_event("PUT", f"/api/projects/{FAKE_UUID}", body={"title": "x"}))
    assert result["statusCode"] == 404


def test_int_put_person_not_found(mocker, integration_db):
    h = integration_handler("people", mocker, integration_db)
    result = h.handler(make_event("PUT", f"/api/people/{FAKE_UUID}", body={"name": "x"}))
    assert result["statusCode"] == 404


def test_int_put_assignment_not_found(mocker, integration_db):
    h = integration_handler("assignments", mocker, integration_db)
    result = h.handler(make_event("PUT", f"/api/assignments/{FAKE_UUID}",
                                    body={"hours_per_week": 5}))
    assert result["statusCode"] == 404


def test_int_put_deliverable_not_found(mocker, integration_db):
    h = integration_handler("deliverables", mocker, integration_db)
    result = h.handler(make_event("PUT", f"/api/deliverables/{FAKE_UUID}",
                                    body={"title": "x"}))
    assert result["statusCode"] == 404


def test_int_put_budget_not_found(mocker, integration_db):
    h = integration_handler("budgets", mocker, integration_db)
    result = h.handler(make_event("PUT", f"/api/budgets/{FAKE_UUID}",
                                    body={"amount_consumed": 1}))
    assert result["statusCode"] == 404


# ---------- projects filter coverage ----------------------------------------

def test_int_project_filter_by_status_and_search(mocker, integration_db):
    h = integration_handler("projects", mocker, integration_db)
    _insert_project(integration_db, title="Apple Cart", status="active")
    _insert_project(integration_db, title="Banana Stand", status="completed")

    by_status = h.handler(make_event("GET", "/api/projects", params={"status": "completed"}))
    assert by_status["statusCode"] == 200
    titles = [p["title"] for p in _body(by_status)["data"]]
    assert "Banana Stand" in titles
    assert "Apple Cart" not in titles

    by_search = h.handler(make_event("GET", "/api/projects", params={"search": "apple"}))
    assert by_search["statusCode"] == 200
    titles2 = [p["title"] for p in _body(by_search)["data"]]
    assert "Apple Cart" in titles2


def test_int_get_person_allocation(mocker, integration_db):
    h = integration_handler("people", mocker, integration_db)
    project_id = _insert_project(integration_db, title="Alloc Proj")
    person_id = _insert_person(integration_db, weekly_hours_capacity=20)
    with integration_db.cursor() as cur:
        cur.execute(
            "INSERT INTO assignments (person_id, project_id, hours_per_week) VALUES (%s, %s, %s)",
            (person_id, project_id, 30),
        )
    result = h.handler(make_event("GET", f"/api/people/{person_id}/allocation"))
    assert result["statusCode"] == 200, _body(result)
    data = _body(result)["data"]
    assert data["allocated_hours_per_week"] == 30
    assert data["is_overallocated"] is True
    assert len(data["assignments"]) == 1

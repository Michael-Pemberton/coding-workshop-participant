"""Error-handling tests — validation, bad input, and edge-case error paths.

These are pure unit tests (use mock_conn). Run with the rest of the suite:
    cd backend && IS_LOCAL=true JWT_SECRET=test-secret python -m pytest tests/ -v
"""

import json

from tests.conftest import load_handler, make_event


# ---------- assignments ------------------------------------------------------

assign = load_handler("assignments")


def test_assignment_hours_out_of_range(mocker, mock_conn):
    mocker.patch.object(assign, "get_db", return_value=mock_conn)
    result = assign.handler(make_event("POST", "/api/assignments", body={
        "person_id": "00000000-0000-0000-0000-000000000001",
        "project_id": "00000000-0000-0000-0000-000000000002",
        "hours_per_week": 999,
    }))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert "hours_per_week" in body["error"]


def test_assignment_hours_not_integer(mocker, mock_conn):
    mocker.patch.object(assign, "get_db", return_value=mock_conn)
    result = assign.handler(make_event("POST", "/api/assignments", body={
        "person_id": "00000000-0000-0000-0000-000000000001",
        "project_id": "00000000-0000-0000-0000-000000000002",
        "hours_per_week": "lots",
    }))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400


def test_assignment_invalid_uuid(mocker, mock_conn):
    mocker.patch.object(assign, "get_db", return_value=mock_conn)
    result = assign.handler(make_event("POST", "/api/assignments", body={
        "person_id": "not-a-uuid",
        "project_id": "00000000-0000-0000-0000-000000000002",
    }))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert "UUID" in body["error"]


def test_assignment_bad_date_format(mocker, mock_conn):
    mocker.patch.object(assign, "get_db", return_value=mock_conn)
    result = assign.handler(make_event("POST", "/api/assignments", body={
        "person_id": "00000000-0000-0000-0000-000000000001",
        "project_id": "00000000-0000-0000-0000-000000000002",
        "start_date": "yesterday",
    }))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert "start_date" in body["error"]


def test_assignment_bad_pagination_params(mocker, mock_conn):
    mocker.patch.object(assign, "get_db", return_value=mock_conn)
    result = assign.handler(make_event(
        "GET", "/api/assignments", params={"limit": "abc"},
    ))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400


# ---------- budgets ----------------------------------------------------------

budgets = load_handler("budgets")


def test_budget_negative_amount(mocker, mock_conn):
    mocker.patch.object(budgets, "get_db", return_value=mock_conn)
    result = budgets.handler(make_event("POST", "/api/budgets", body={
        "project_id": "00000000-0000-0000-0000-000000000001",
        "category": "staff",
        "amount_planned": -10,
    }))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert "negative" in body["error"]


def test_budget_invalid_category(mocker, mock_conn):
    mocker.patch.object(budgets, "get_db", return_value=mock_conn)
    result = budgets.handler(make_event("POST", "/api/budgets", body={
        "project_id": "00000000-0000-0000-0000-000000000001",
        "category": "not-a-real-category",
    }))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert "category" in body["error"]


def test_budget_amount_not_a_number(mocker, mock_conn):
    mocker.patch.object(budgets, "get_db", return_value=mock_conn)
    result = budgets.handler(make_event("POST", "/api/budgets", body={
        "project_id": "00000000-0000-0000-0000-000000000001",
        "category": "staff",
        "amount_consumed": "lots",
    }))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400


# ---------- deliverables -----------------------------------------------------

deliv = load_handler("deliverables")


def test_deliverable_bad_due_date(mocker, mock_conn):
    mocker.patch.object(deliv, "get_db", return_value=mock_conn)
    result = deliv.handler(make_event("POST", "/api/deliverables", body={
        "title": "X",
        "project_id": "00000000-0000-0000-0000-000000000001",
        "due_date": "not-a-date",
    }))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert "due_date" in body["error"]


def test_deliverable_bad_pagination(mocker, mock_conn):
    mocker.patch.object(deliv, "get_db", return_value=mock_conn)
    result = deliv.handler(make_event(
        "GET", "/api/deliverables", params={"offset": "x"},
    ))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400


# ---------- projects ---------------------------------------------------------

projects = load_handler("projects")


def test_project_empty_title_after_strip(mocker, mock_conn):
    mocker.patch.object(projects, "get_db", return_value=mock_conn)
    result = projects.handler(make_event("POST", "/api/projects", body={"title": "    "}))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert "title" in body["error"]


# ---------- people -----------------------------------------------------------

people = load_handler("people")


def test_people_invalid_json(mocker, mock_conn):
    mocker.patch.object(people, "get_db", return_value=mock_conn)
    event = make_event("POST", "/api/people")
    event["body"] = "{not json"
    result = people.handler(event)
    body = json.loads(result["body"])
    assert result["statusCode"] == 400


def test_people_invalid_email_format(mocker, mock_conn):
    mocker.patch.object(people, "get_db", return_value=mock_conn)
    result = people.handler(make_event("POST", "/api/people", body={
        "name": "X", "email": "not-an-email",
    }))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert "email" in body["error"]


def test_people_capacity_out_of_range(mocker, mock_conn):
    mocker.patch.object(people, "get_db", return_value=mock_conn)
    result = people.handler(make_event("POST", "/api/people", body={
        "name": "X", "email": "x@y.com", "weekly_hours_capacity": 999,
    }))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert "weekly_hours_capacity" in body["error"]


def test_people_capacity_not_integer(mocker, mock_conn):
    mocker.patch.object(people, "get_db", return_value=mock_conn)
    result = people.handler(make_event("POST", "/api/people", body={
        "name": "X", "email": "x@y.com", "weekly_hours_capacity": "lots",
    }))
    assert result["statusCode"] == 400


def test_people_negative_hourly_pay(mocker, mock_conn):
    mocker.patch.object(people, "get_db", return_value=mock_conn)
    result = people.handler(make_event("POST", "/api/people", body={
        "name": "X", "email": "x@y.com", "hourly_pay": -5,
    }))
    assert result["statusCode"] == 400


# ---------- projects extra validation ---------------------------------------

def test_project_invalid_status_value(mocker, mock_conn):
    mocker.patch.object(projects, "get_db", return_value=mock_conn)
    result = projects.handler(make_event("POST", "/api/projects", body={
        "title": "X", "status": "not-a-status",
    }))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert "status" in body["error"]


def test_project_negative_budget(mocker, mock_conn):
    mocker.patch.object(projects, "get_db", return_value=mock_conn)
    result = projects.handler(make_event("POST", "/api/projects", body={
        "title": "X", "budget_planned": -100,
    }))
    assert result["statusCode"] == 400


def test_project_bad_date(mocker, mock_conn):
    mocker.patch.object(projects, "get_db", return_value=mock_conn)
    result = projects.handler(make_event("POST", "/api/projects", body={
        "title": "X", "start_date": "not-a-date",
    }))
    assert result["statusCode"] == 400


def test_project_filter_invalid_status_returns_400(mocker, mock_conn):
    mocker.patch.object(projects, "get_db", return_value=mock_conn)
    result = projects.handler(make_event(
        "GET", "/api/projects", params={"status": "bogus"},
    ))
    assert result["statusCode"] == 400


def test_project_filter_invalid_health_returns_400(mocker, mock_conn):
    mocker.patch.object(projects, "get_db", return_value=mock_conn)
    result = projects.handler(make_event(
        "GET", "/api/projects", params={"health": "purple"},
    ))
    assert result["statusCode"] == 400


# ---------- deliverable RAG-with-dependency edge case -----------------------

def test_with_rag_dependency_after_own_due_marks_red():
    row = {
        "due_date": "2030-01-10",
        "depends_on_due_date": "2030-01-20",  # dep due AFTER this one
        "depends_on_title": "Upstream Thing",
    }
    out = deliv._with_rag(row)
    assert out["status"] == "red"
    assert "Upstream Thing" in out["health_reason"]


def test_with_rag_no_dependency_returns_time_based_color():
    row = {"due_date": None}
    out = deliv._with_rag(row)
    assert out["status"] == "green"
    assert out["health_reason"] == "No due date set"

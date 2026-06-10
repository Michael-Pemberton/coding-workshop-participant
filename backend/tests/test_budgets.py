"""Tests for the budgets Lambda handler."""

import json

import pytest

from tests.conftest import load_handler, make_event

handler_mod = load_handler("budgets")


def test_options_preflight():
    result = handler_mod.handler(make_event("OPTIONS", "/api/budgets"))
    assert result["statusCode"] == 204


def test_list_budgets_success(mocker, mock_conn):
    mock_conn._cur.description = [
        ("id",), ("project_id",), ("category",), ("description",),
        ("amount_planned",), ("amount_consumed",), ("is_deleted",),
        ("created_at",), ("updated_at",),
    ]
    mock_conn._cur.fetchall.return_value = []
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(make_event("GET", "/api/budgets"))
    body = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert body["success"] is True
    assert body["data"] == []


def test_create_budget_missing_project_id(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(
        make_event("POST", "/api/budgets", body={"category": "staff", "amount_planned": 5000})
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 400
    assert "project_id" in body["error"]


def test_create_budget_viewer_forbidden(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value={"role": "viewer", "sub": "u1"})

    result = handler_mod.handler(
        make_event("POST", "/api/budgets", body={
            "project_id": "00000000-0000-0000-0000-000000000001",
            "category": "staff",
        })
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 403


def test_delete_budget_viewer_forbidden(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value={"role": "viewer", "sub": "u1"})

    result = handler_mod.handler(
        make_event("DELETE", "/api/budgets/00000000-0000-0000-0000-000000000001")
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 403


def test_unauthenticated_request(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value=None)

    result = handler_mod.handler(make_event("GET", "/api/budgets"))
    body = json.loads(result["body"])

    assert result["statusCode"] == 401


def test_sync_project_budget_executes_update_and_commits(mock_conn):
    project_id = "00000000-0000-0000-0000-000000000001"
    handler_mod.sync_project_budget(mock_conn, project_id)
    mock_conn._cur.execute.assert_called_once()
    sql, params = mock_conn._cur.execute.call_args[0]
    assert "UPDATE projects" in sql
    assert "GREATEST" in sql  # never lowers existing budget_consumed
    assert params == (project_id, project_id)
    mock_conn.commit.assert_called_once()

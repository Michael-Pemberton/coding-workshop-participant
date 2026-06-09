"""Tests for the projects Lambda handler."""

import json

import pytest

from tests.conftest import load_handler, make_event

handler_mod = load_handler("projects")


def test_options_preflight():
    result = handler_mod.handler(make_event("OPTIONS", "/api/projects"))
    assert result["statusCode"] == 204


def test_list_projects_success(mocker, mock_conn):
    mock_conn._cur.description = [
        ("id",), ("title",), ("status",), ("health",), ("start_date",),
        ("end_date",), ("budget_planned",), ("budget_consumed",),
        ("dependency_ids",), ("is_deleted",), ("created_by",),
        ("created_at",), ("updated_at",), ("description",),
    ]
    mock_conn._cur.fetchall.return_value = []
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(make_event("GET", "/api/projects"))
    body = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert body["success"] is True
    assert body["data"] == []


def test_get_project_not_found(mocker, mock_conn):
    mock_conn._cur.fetchone.return_value = None
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(
        make_event("GET", "/api/projects/00000000-0000-0000-0000-000000000001")
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 404
    assert body["success"] is False


def test_create_project_missing_title(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(make_event("POST", "/api/projects", body={"description": "No title"}))
    body = json.loads(result["body"])

    assert result["statusCode"] == 400
    assert "title" in body["error"]


def test_create_project_viewer_forbidden(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value={"role": "viewer", "sub": "u1"})

    result = handler_mod.handler(make_event("POST", "/api/projects", body={"title": "Project X"}))
    body = json.loads(result["body"])

    assert result["statusCode"] == 403


def test_create_project_invalid_json(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    event = make_event("POST", "/api/projects")
    event["body"] = "not-json"
    result = handler_mod.handler(event)
    body = json.loads(result["body"])

    assert result["statusCode"] == 400
    assert "JSON" in body["error"]


def test_delete_project_non_admin(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value={"role": "manager", "sub": "u1"})

    result = handler_mod.handler(
        make_event("DELETE", "/api/projects/00000000-0000-0000-0000-000000000001")
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 403
    assert "Admin" in body["error"]


def test_unauthenticated_request(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value=None)

    result = handler_mod.handler(make_event("GET", "/api/projects"))
    body = json.loads(result["body"])

    assert result["statusCode"] == 401


def test_method_not_allowed(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(make_event("PATCH", "/api/projects"))
    body = json.loads(result["body"])

    assert result["statusCode"] == 405

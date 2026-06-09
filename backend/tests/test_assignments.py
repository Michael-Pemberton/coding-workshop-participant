"""Tests for the assignments Lambda handler."""

import json

import pytest

from tests.conftest import load_handler, make_event

handler_mod = load_handler("assignments")


def test_options_preflight():
    result = handler_mod.handler(make_event("OPTIONS", "/api/assignments"))
    assert result["statusCode"] == 204


def test_list_assignments_success(mocker, mock_conn):
    mock_conn._cur.description = [
        ("id",), ("person_id",), ("project_id",), ("role_on_project",),
        ("hours_per_week",), ("start_date",), ("end_date",), ("is_deleted",),
        ("created_at",), ("updated_at",), ("person_name",), ("person_email",),
        ("project_title",),
    ]
    mock_conn._cur.fetchall.return_value = []
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(make_event("GET", "/api/assignments"))
    body = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert body["success"] is True
    assert body["data"] == []


def test_create_assignment_missing_fields(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(
        make_event("POST", "/api/assignments", body={"person_id": "abc"})
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 400
    assert "project_id" in body["error"]


def test_create_assignment_viewer_forbidden(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value={"role": "viewer", "sub": "u1"})

    result = handler_mod.handler(
        make_event("POST", "/api/assignments", body={
            "person_id": "00000000-0000-0000-0000-000000000001",
            "project_id": "00000000-0000-0000-0000-000000000002",
        })
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 403


def test_delete_assignment_viewer_forbidden(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value={"role": "viewer", "sub": "u1"})

    result = handler_mod.handler(
        make_event("DELETE", "/api/assignments/00000000-0000-0000-0000-000000000001")
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 403


def test_unauthenticated_request(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value=None)

    result = handler_mod.handler(make_event("GET", "/api/assignments"))
    body = json.loads(result["body"])

    assert result["statusCode"] == 401

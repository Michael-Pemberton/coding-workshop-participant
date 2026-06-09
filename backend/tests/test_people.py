"""Tests for the people Lambda handler."""

import json

import pytest

from tests.conftest import load_handler, make_event

handler_mod = load_handler("people")


def test_options_preflight():
    result = handler_mod.handler(make_event("OPTIONS", "/api/people"))
    assert result["statusCode"] == 204


def test_list_people_success(mocker, mock_conn):
    mock_conn._cur.description = [
        ("id",), ("name",), ("email",), ("title",), ("weekly_hours_capacity",),
        ("is_active",), ("is_deleted",), ("created_at",), ("updated_at",),
        ("allocated_hours_per_week",),
    ]
    mock_conn._cur.fetchall.return_value = []
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(make_event("GET", "/api/people"))
    body = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert body["success"] is True
    assert body["data"] == []


def test_get_person_not_found(mocker, mock_conn):
    mock_conn._cur.fetchone.return_value = None
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(
        make_event("GET", "/api/people/00000000-0000-0000-0000-000000000001")
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 404
    assert body["success"] is False


def test_create_person_missing_name(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(
        make_event("POST", "/api/people", body={"email": "test@example.com"})
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 400
    assert "name" in body["error"]


def test_create_person_missing_email(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(
        make_event("POST", "/api/people", body={"name": "Alice"})
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 400
    assert "email" in body["error"]


def test_create_person_viewer_forbidden(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value={"role": "viewer", "sub": "u1"})

    result = handler_mod.handler(
        make_event("POST", "/api/people", body={"name": "Alice", "email": "alice@example.com"})
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 403


def test_delete_person_non_admin(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value={"role": "manager", "sub": "u1"})

    result = handler_mod.handler(
        make_event("DELETE", "/api/people/00000000-0000-0000-0000-000000000001")
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 403
    assert "Admin" in body["error"]


def test_unauthenticated_request(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value=None)

    result = handler_mod.handler(make_event("GET", "/api/people"))
    body = json.loads(result["body"])

    assert result["statusCode"] == 401

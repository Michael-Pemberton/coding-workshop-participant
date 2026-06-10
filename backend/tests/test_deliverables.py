"""Tests for the deliverables Lambda handler."""

import json

import pytest

from tests.conftest import load_handler, make_event

handler_mod = load_handler("deliverables")


def test_options_preflight():
    result = handler_mod.handler(make_event("OPTIONS", "/api/deliverables"))
    assert result["statusCode"] == 204


def test_list_deliverables_success(mocker, mock_conn):
    mock_conn._cur.description = [
        ("id",), ("project_id",), ("title",), ("description",), ("status",),
        ("due_date",), ("depends_on_id",), ("is_deleted",), ("created_at",),
        ("updated_at",), ("depends_on_title",),
    ]
    mock_conn._cur.fetchall.return_value = []
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(make_event("GET", "/api/deliverables"))
    body = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert body["success"] is True
    assert body["data"] == []


def test_create_deliverable_missing_title(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(
        make_event("POST", "/api/deliverables", body={"project_id": "00000000-0000-0000-0000-000000000001"})
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 400
    assert "title" in body["error"]


def test_create_deliverable_missing_project_id(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)

    result = handler_mod.handler(
        make_event("POST", "/api/deliverables", body={"title": "Milestone 1"})
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 400
    assert "project_id" in body["error"]


def test_create_deliverable_viewer_forbidden(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value={"role": "viewer", "sub": "u1"})

    result = handler_mod.handler(
        make_event("POST", "/api/deliverables", body={
            "title": "Milestone",
            "project_id": "00000000-0000-0000-0000-000000000001",
        })
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 403


def test_delete_deliverable_viewer_forbidden(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value={"role": "viewer", "sub": "u1"})

    result = handler_mod.handler(
        make_event("DELETE", "/api/deliverables/00000000-0000-0000-0000-000000000001")
    )
    body = json.loads(result["body"])

    assert result["statusCode"] == 403


def test_unauthenticated_request(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user", return_value=None)

    result = handler_mod.handler(make_event("GET", "/api/deliverables"))
    body = json.loads(result["body"])

    assert result["statusCode"] == 401


def test_would_cycle_self_reference(mock_conn):
    item_id = "00000000-0000-0000-0000-000000000001"
    assert handler_mod._would_cycle(mock_conn, item_id, item_id) is True


def test_would_cycle_no_dependency(mock_conn):
    assert handler_mod._would_cycle(mock_conn, "any", None) is False


def test_would_cycle_detects_loop_in_chain(mock_conn):
    a = "00000000-0000-0000-0000-00000000000a"
    b = "00000000-0000-0000-0000-00000000000b"
    # Inserting a new deliverable (item_id=None) whose depends_on_id = b,
    # and b depends on a, and a depends on b → cycle.
    mock_conn._cur.fetchone.side_effect = [(a,), (b,)]
    assert handler_mod._would_cycle(mock_conn, None, b) is True


def test_would_cycle_clean_chain_returns_false(mock_conn):
    a = "00000000-0000-0000-0000-00000000000a"
    b = "00000000-0000-0000-0000-00000000000b"
    # b → a → (none)
    mock_conn._cur.fetchone.side_effect = [(a,), (None,)]
    assert handler_mod._would_cycle(mock_conn, None, b) is False

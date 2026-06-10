"""Tests for the auth Lambda handler."""

from datetime import datetime, timedelta, timezone

import jwt

from tests.conftest import load_handler, make_event

handler_mod = load_handler("auth")


def _bearer_event(token: str) -> dict:
    return {"headers": {"Authorization": f"Bearer {token}"}}


def test_get_user_from_token_expired_returns_none():
    payload = {
        "sub": "u1",
        "email": "a@b.com",
        "exp": datetime.now(tz=timezone.utc) - timedelta(seconds=1),
    }
    token = jwt.encode(payload, handler_mod.JWT_SECRET, algorithm="HS256")
    assert handler_mod.get_user_from_token(_bearer_event(token)) is None


def test_get_user_from_token_invalid_signature_returns_none():
    payload = {"sub": "u1", "exp": datetime.now(tz=timezone.utc) + timedelta(hours=1)}
    token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
    assert handler_mod.get_user_from_token(_bearer_event(token)) is None


def test_get_user_from_token_valid_returns_payload():
    payload = {
        "sub": "u1",
        "email": "a@b.com",
        "exp": datetime.now(tz=timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(payload, handler_mod.JWT_SECRET, algorithm="HS256")
    result = handler_mod.get_user_from_token(_bearer_event(token))
    assert result is not None
    assert result["sub"] == "u1"


def test_get_user_from_token_missing_bearer_returns_none():
    assert handler_mod.get_user_from_token({"headers": {}}) is None


# ---------- make_jwt ---------------------------------------------------------

def test_make_jwt_round_trips_user_fields():
    user = {"id": "u-1", "email": "x@y.com", "name": "X", "user_role": "manager"}
    token = handler_mod.make_jwt(user)
    decoded = jwt.decode(token, handler_mod.JWT_SECRET, algorithms=["HS256"])
    assert decoded["sub"] == "u-1"
    assert decoded["email"] == "x@y.com"
    assert decoded["role"] == "manager"
    assert "exp" in decoded


# ---------- rate limiter -----------------------------------------------------

def test_rate_limiter_not_triggered_below_threshold():
    handler_mod._failed_attempts.clear()
    for _ in range(handler_mod._MAX_ATTEMPTS - 1):
        handler_mod._record_failure("rl-user-a")
    assert handler_mod._check_rate_limit("rl-user-a") is False


def test_rate_limiter_triggers_at_threshold():
    handler_mod._failed_attempts.clear()
    for _ in range(handler_mod._MAX_ATTEMPTS):
        handler_mod._record_failure("rl-user-b")
    assert handler_mod._check_rate_limit("rl-user-b") is True


def test_rate_limiter_clear_failures_resets():
    handler_mod._failed_attempts.clear()
    for _ in range(handler_mod._MAX_ATTEMPTS):
        handler_mod._record_failure("rl-user-c")
    handler_mod._clear_failures("rl-user-c")
    assert handler_mod._check_rate_limit("rl-user-c") is False


def test_rate_limiter_window_expires(mocker):
    handler_mod._failed_attempts.clear()
    past = datetime.now(tz=timezone.utc) - timedelta(seconds=handler_mod._LOCKOUT_SECONDS + 60)
    handler_mod._failed_attempts["rl-user-d"] = (handler_mod._MAX_ATTEMPTS, past)
    # _check_rate_limit should detect the expired window and clear the entry.
    assert handler_mod._check_rate_limit("rl-user-d") is False
    assert "rl-user-d" not in handler_mod._failed_attempts


# ---------- input validation (no DB needed) ---------------------------------

def test_login_missing_username_or_password(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    result = handler_mod.handler(make_event("POST", "/api/auth/login", body={"username": "u"}))
    assert result["statusCode"] == 400


def test_create_user_short_password(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    result = handler_mod.create_user({
        "username": "u", "name": "n", "email": "e@x.com", "password": "short", "role": "viewer",
    })
    assert result["statusCode"] == 400
    assert "8 characters" in __import__("json").loads(result["body"])["error"]


def test_create_user_invalid_role(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    result = handler_mod.create_user({
        "username": "u", "name": "n", "email": "e@x.com", "password": "longenough",
        "role": "wizard",
    })
    assert result["statusCode"] == 400


def test_create_user_missing_fields(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    result = handler_mod.create_user({"username": "u"})
    assert result["statusCode"] == 400


def test_delete_user_self_blocked(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    result = handler_mod.delete_user("user-1", "user-1")
    assert result["statusCode"] == 400


def test_handler_non_admin_cannot_list_users(mocker, mock_conn):
    mocker.patch.object(handler_mod, "get_db", return_value=mock_conn)
    mocker.patch.object(handler_mod, "get_user_from_token",
                         return_value={"role": "viewer", "sub": "u", "email": "v@x.com"})
    event = make_event("GET", "/api/auth/users")
    event["headers"] = {"Authorization": "Bearer x"}
    # IS_LOCAL bypass would normally make this admin; force the token-based path.
    mocker.patch.object(handler_mod, "IS_LOCAL", False)
    result = handler_mod.handler(event)
    assert result["statusCode"] == 403


def test_handler_options_returns_204():
    result = handler_mod.handler(make_event("OPTIONS", "/api/auth/verify"))
    assert result["statusCode"] == 204

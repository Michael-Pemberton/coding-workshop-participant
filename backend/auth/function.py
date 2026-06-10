"""Auth Lambda — username/password login, JWT issuance, user management."""

import json
import logging
from datetime import datetime, timedelta, timezone

import jwt

from shared import (
    get_db, resp, extract_id, rows_to_dicts, row_to_dict, IS_LOCAL, JWT_SECRET,
    hash_password, verify_password, init_db,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Simple in-memory rate limiter for the password login endpoint.
# Tracks failed attempts per username: {username: (count, first_failure_ts)}
_failed_attempts: dict = {}
_MAX_ATTEMPTS = 10
_LOCKOUT_SECONDS = 300  # 5 minutes


def _check_rate_limit(username: str) -> bool:
    """Returns True if the username is currently locked out."""
    entry = _failed_attempts.get(username)
    if not entry:
        return False
    count, first_ts = entry
    elapsed = (datetime.now(tz=timezone.utc) - first_ts).total_seconds()
    if elapsed > _LOCKOUT_SECONDS:
        del _failed_attempts[username]
        return False
    return count >= _MAX_ATTEMPTS


def _record_failure(username: str):
    entry = _failed_attempts.get(username)
    now = datetime.now(tz=timezone.utc)
    if entry:
        count, first_ts = entry
        elapsed = (now - first_ts).total_seconds()
        if elapsed > _LOCKOUT_SECONDS:
            _failed_attempts[username] = (1, now)
        else:
            _failed_attempts[username] = (count + 1, first_ts)
    else:
        _failed_attempts[username] = (1, now)


def _clear_failures(username: str):
    _failed_attempts.pop(username, None)


def get_user_from_token(event: dict):
    """Validates Bearer JWT from request headers (no IS_LOCAL bypass)."""
    headers = event.get("headers") or {}
    auth = headers.get("authorization") or headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        return jwt.decode(auth[7:], JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning("Invalid JWT token: %s", exc)
        return None


def make_jwt(user: dict) -> str:
    """Creates a signed JWT with 24-hour expiry."""
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "name": user["name"],
        "role": user["user_role"],
        "exp": datetime.now(tz=timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


VALID_ROLES = ("admin", "manager", "contributor", "viewer")


def login_with_password(body: dict) -> dict:
    """POST /api/auth/login — username + password login with rate limiting."""
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not username or not password:
        return resp(400, {"error": "username and password are required", "success": False})

    if _check_rate_limit(username):
        return resp(429, {"error": "Too many failed attempts. Try again later.", "success": False})

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        if not row:
            _record_failure(username)
            return resp(401, {"error": "Invalid credentials", "success": False})
        user = row_to_dict(cur, row)
    if not user.get("is_active", True):
        return resp(403, {"error": "Account is inactive", "success": False})
    if not verify_password(password, user.get("password_hash") or ""):
        _record_failure(username)
        return resp(401, {"error": "Invalid credentials", "success": False})
    _clear_failures(username)
    token = make_jwt(user)
    user.pop("password_hash", None)
    return resp(200, {"data": {"token": token, "user": user}, "success": True})


def create_user(body: dict) -> dict:
    """POST /api/auth/users — admin creates a new user."""
    username = (body.get("username") or "").strip()
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    role = body.get("role") or "viewer"
    if not username or not name or not email or not password:
        return resp(400, {"error": "username, name, email, and password are required", "success": False})
    if role not in VALID_ROLES:
        return resp(400, {"error": f"role must be one of: {VALID_ROLES}", "success": False})
    if len(password) < 8:
        return resp(400, {"error": "password must be at least 8 characters", "success": False})
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE username = %s OR email = %s", (username, email))
        if cur.fetchone():
            return resp(409, {"error": "username or email already exists", "success": False})
        cur.execute(
            "INSERT INTO users (username, name, email, password_hash, user_role) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING *",
            (username, name, email, hash_password(password), role),
        )
        row = cur.fetchone()
        conn.commit()
        user = row_to_dict(cur, row)
        user.pop("password_hash", None)
        return resp(201, {"data": user, "success": True})


def update_user(user_id: str, body: dict) -> dict:
    """PUT /api/auth/users/{id} — admin updates a user (role/name/email/username/password)."""
    fields = []
    values = []
    if "name" in body and body["name"]:
        fields.append("name = %s")
        values.append(body["name"].strip())
    if "email" in body and body["email"]:
        fields.append("email = %s")
        values.append(body["email"].strip().lower())
    if "username" in body and body["username"]:
        fields.append("username = %s")
        values.append(body["username"].strip())
    if "role" in body and body["role"]:
        if body["role"] not in VALID_ROLES:
            return resp(400, {"error": f"role must be one of: {VALID_ROLES}", "success": False})
        fields.append("user_role = %s")
        values.append(body["role"])
    if body.get("password"):
        if len(body["password"]) < 8:
            return resp(400, {"error": "password must be at least 8 characters", "success": False})
        fields.append("password_hash = %s")
        values.append(hash_password(body["password"]))
    if "is_active" in body:
        fields.append("is_active = %s")
        values.append(bool(body["is_active"]))
    if not fields:
        return resp(400, {"error": "no fields to update", "success": False})
    fields.append("updated_at = NOW()")
    values.append(user_id)
    conn = get_db()
    with conn.cursor() as cur:
        try:
            cur.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE id = %s RETURNING *",
                tuple(values),
            )
        except Exception as exc:
            conn.rollback()
            return resp(409, {"error": f"update failed: {exc}", "success": False})
        row = cur.fetchone()
        if not row:
            return resp(404, {"error": "User not found", "success": False})
        conn.commit()
        user = row_to_dict(cur, row)
        user.pop("password_hash", None)
        return resp(200, {"data": user, "success": True})


def delete_user(user_id: str, requester_id: str) -> dict:
    """DELETE /api/auth/users/{id} — admin deactivates a user (no self-delete)."""
    if str(user_id) == str(requester_id):
        return resp(400, {"error": "Cannot deactivate yourself", "success": False})
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET is_active = FALSE, updated_at = NOW() WHERE id = %s RETURNING id",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return resp(404, {"error": "User not found", "success": False})
        conn.commit()
        return resp(200, {"data": {"id": user_id}, "success": True})


def handler(event=None, context=None):
    """Routes auth requests."""
    if event is None:
        event = {}

    # One-shot bootstrap: invoke directly with {"action": "init"} to create
    # the schema and seed an admin. Not reachable via API Gateway / Function URL.
    if event.get("action") == "init":
        init_db()
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            count = cur.fetchone()[0]
            seeded = False
            if count == 0:
                cur.execute(
                    "INSERT INTO users (username, name, email, password_hash, user_role) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    ("admin", "Admin", "admin@acme.com", hash_password("admin123"), "admin"),
                )
                conn.commit()
                seeded = True
        return {"ok": True, "seeded_admin": seeded, "user_count": count + (1 if seeded else 0)}

    method = (event.get("requestContext") or {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "")

    if method == "OPTIONS":
        return resp(204, {})

    conn = get_db()

    try:
        if method == "POST" and path.endswith("/login"):
            body = json.loads(event.get("body") or "{}")
            return login_with_password(body)

        user_payload = get_user_from_token(event)
        if not user_payload and not IS_LOCAL:
            return resp(401, {"error": "Authentication required", "success": False})
        if IS_LOCAL and not user_payload:
            user_payload = {"sub": "dev-user", "email": "admin@acme.com", "name": "Dev Admin", "role": "admin"}

        if method == "GET" and "me" in path:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (user_payload["email"],))
                row = cur.fetchone()
                if not row:
                    return resp(404, {"error": "User not found", "success": False})
                user = row_to_dict(cur, row)
                user.pop("password_hash", None)
                return resp(200, {"data": user, "success": True})

        if method == "GET" and "users" in path:
            if user_payload.get("role") != "admin":
                return resp(403, {"error": "Admin role required", "success": False})
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users ORDER BY name")
                rows = rows_to_dicts(cur)
                for r in rows:
                    r.pop("password_hash", None)
                return resp(200, {"data": rows, "success": True})

        if method == "POST" and "users" in path:
            if user_payload.get("role") != "admin":
                return resp(403, {"error": "Admin role required", "success": False})
            body = json.loads(event.get("body") or "{}")
            return create_user(body)

        if method == "PUT" and "role" in path:
            if user_payload.get("role") != "admin":
                return resp(403, {"error": "Admin role required", "success": False})
            user_id = extract_id(path)
            if not user_id:
                return resp(400, {"error": "User ID required", "success": False})
            body = json.loads(event.get("body") or "{}")
            new_role = body.get("role")
            if new_role not in VALID_ROLES:
                return resp(400, {"error": f"role must be one of: {VALID_ROLES}", "success": False})
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET user_role = %s, updated_at = NOW() WHERE id = %s RETURNING *",
                    (new_role, user_id),
                )
                row = cur.fetchone()
                conn.commit()
                if not row:
                    return resp(404, {"error": "User not found", "success": False})
                user = row_to_dict(cur, row)
                user.pop("password_hash", None)
                return resp(200, {"data": user, "success": True})

        if method == "PUT" and "users" in path:
            if user_payload.get("role") != "admin":
                return resp(403, {"error": "Admin role required", "success": False})
            user_id = extract_id(path)
            if not user_id:
                return resp(400, {"error": "User ID required", "success": False})
            body = json.loads(event.get("body") or "{}")
            return update_user(user_id, body)

        if method == "DELETE" and "users" in path:
            if user_payload.get("role") != "admin":
                return resp(403, {"error": "Admin role required", "success": False})
            user_id = extract_id(path)
            if not user_id:
                return resp(400, {"error": "User ID required", "success": False})
            return delete_user(user_id, user_payload.get("sub"))

        return resp(404, {"error": "Not found", "success": False})
    except Exception as exc:
        logger.error("Error: %s", exc, exc_info=True)
        return resp(500, {"error": f"{type(exc).__name__}: {exc}", "success": False})


if __name__ == "__main__":
    print(handler({"requestContext": {"http": {"method": "GET"}}, "rawPath": "/api/auth/me"}))

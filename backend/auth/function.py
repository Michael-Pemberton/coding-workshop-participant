"""Auth Lambda — Google OAuth verification and user management."""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import jwt
import requests

from shared import (
    get_db, resp, extract_id, rows_to_dicts, row_to_dict, init_db, IS_LOCAL, JWT_SECRET,
    hash_password, verify_password,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

try:
    init_db()
except Exception as exc:
    logger.error("DB init failed: %s", exc)


def get_user_from_token(event: dict):
    """Validates Bearer JWT from request headers (no IS_LOCAL bypass)."""
    headers = event.get("headers") or {}
    auth = headers.get("authorization") or headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        return jwt.decode(auth[7:], JWT_SECRET, algorithms=["HS256"])
    except Exception:
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


def upsert_user(conn, email: str, name: str, picture: str = None) -> dict:
    """Finds or creates a user by email, returns the user record."""
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        if row:
            return row_to_dict(cur, row)
        cur.execute(
            "INSERT INTO users (email, name, picture) VALUES (%s, %s, %s) RETURNING *",
            (email, name, picture),
        )
        row = cur.fetchone()
        conn.commit()
        return row_to_dict(cur, row)


def verify_google_token(body: dict) -> dict:
    """POST /api/auth/verify — verifies a Google ID token or handles dev bypass."""
    conn = get_db()

    if body.get("dev_login") and IS_LOCAL:
        email = body.get("email", "admin@acme.com")
        name = body.get("name", "Dev Admin")
        user = upsert_user(conn, email, name)
        if user["user_role"] != "admin":
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET user_role = 'admin' WHERE id = %s RETURNING *",
                    (user["id"],),
                )
                row = cur.fetchone()
                conn.commit()
                user = row_to_dict(cur, row)
        token = make_jwt(user)
        return resp(200, {"data": {"token": token, "user": user}, "success": True})

    credential = body.get("credential")
    if not credential:
        return resp(400, {"error": "credential is required", "success": False})

    try:
        google_resp = requests.get(
            f"https://www.googleapis.com/oauth2/v3/tokeninfo?id_token={credential}",
            timeout=10,
        )
        if google_resp.status_code != 200:
            return resp(401, {"error": "Invalid Google token", "success": False})
        claims = google_resp.json()
        if GOOGLE_CLIENT_ID and claims.get("aud") != GOOGLE_CLIENT_ID:
            return resp(401, {"error": "Token audience mismatch", "success": False})
        email = claims.get("email")
        name = claims.get("name", email)
        picture = claims.get("picture")
    except requests.RequestException as exc:
        logger.error("Google token verification failed: %s", exc)
        return resp(502, {"error": "Failed to verify token with Google", "success": False})

    user = upsert_user(conn, email, name, picture)
    token = make_jwt(user)
    return resp(200, {"data": {"token": token, "user": user}, "success": True})


VALID_ROLES = ("admin", "manager", "contributor", "viewer")


def login_with_password(body: dict) -> dict:
    """POST /api/auth/login — username + password login."""
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not username or not password:
        return resp(400, {"error": "username and password are required", "success": False})
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        if not row:
            return resp(401, {"error": "Invalid credentials", "success": False})
        user = row_to_dict(cur, row)
    if not user.get("is_active", True):
        return resp(403, {"error": "Account is inactive", "success": False})
    if not verify_password(password, user.get("password_hash") or ""):
        return resp(401, {"error": "Invalid credentials", "success": False})
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
    method = (event.get("requestContext") or {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "")

    if method == "OPTIONS":
        return resp(204, {})

    conn = get_db()

    try:
        if method == "POST" and path.endswith("/login"):
            body = json.loads(event.get("body") or "{}")
            return login_with_password(body)

        if method == "POST" and "verify" in path:
            body = json.loads(event.get("body") or "{}")
            return verify_google_token(body)

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
        return resp(500, {"error": "Internal server error", "success": False})


if __name__ == "__main__":
    print(handler({"requestContext": {"http": {"method": "POST"}}, "rawPath": "/api/auth/verify", "body": '{"dev_login": true}'}))

"""Shared utilities for all Lambda handlers — imported by each service at runtime."""

import json
import logging
import os
import re
from datetime import date

import psycopg
import jwt

logger = logging.getLogger(__name__)

IS_LOCAL = os.getenv("IS_LOCAL", "false") == "true"
JWT_SECRET = os.getenv("JWT_SECRET", "")

# Fail fast: refuse to start in production without a real secret.
if not IS_LOCAL and not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable must be set in production.")
if not JWT_SECRET:
    JWT_SECRET = "dev-secret-key-change-in-production"

# Allowed CORS origins — set CORS_ORIGIN env var in production.
CORS_ORIGIN = os.getenv("CORS_ORIGIN", "*")

_conn = None

DDL = """
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE TABLE IF NOT EXISTS users (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email VARCHAR(255) UNIQUE NOT NULL, name VARCHAR(255) NOT NULL, user_role VARCHAR(50) NOT NULL DEFAULT 'viewer', is_active BOOLEAN DEFAULT TRUE, username VARCHAR(100) UNIQUE, password_hash TEXT, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(100) UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE users DROP COLUMN IF EXISTS picture;
CREATE TABLE IF NOT EXISTS projects (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), title VARCHAR(255) NOT NULL, description TEXT, status VARCHAR(50) NOT NULL DEFAULT 'active', health VARCHAR(50) NOT NULL DEFAULT 'green', start_date DATE, end_date DATE, budget_planned DECIMAL(15,2) DEFAULT 0.00, budget_consumed DECIMAL(15,2) DEFAULT 0.00, dependency_ids UUID[] DEFAULT '{}', is_deleted BOOLEAN DEFAULT FALSE, created_by UUID, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
CREATE TABLE IF NOT EXISTS people (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR(255) NOT NULL, email VARCHAR(255) UNIQUE NOT NULL, title VARCHAR(100), weekly_hours_capacity INTEGER DEFAULT 40, hourly_pay DECIMAL(15,2), is_active BOOLEAN DEFAULT TRUE, is_deleted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
ALTER TABLE people ADD COLUMN IF NOT EXISTS hourly_pay DECIMAL(15,2);
CREATE TABLE IF NOT EXISTS assignments (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), person_id UUID NOT NULL, project_id UUID NOT NULL, role_on_project VARCHAR(100), hours_per_week INTEGER DEFAULT 0, start_date DATE, end_date DATE, is_deleted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
CREATE TABLE IF NOT EXISTS deliverables (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID NOT NULL, title VARCHAR(255) NOT NULL, description TEXT, status VARCHAR(50) NOT NULL DEFAULT 'pending', due_date DATE, depends_on_id UUID, is_deleted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
CREATE TABLE IF NOT EXISTS staff_budget_overrides (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID NOT NULL, person_id UUID NOT NULL, amount_planned DECIMAL(15,2), amount_consumed DECIMAL(15,2), is_deleted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), UNIQUE(project_id, person_id));
CREATE TABLE IF NOT EXISTS budget_items (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID NOT NULL, category VARCHAR(100) NOT NULL DEFAULT 'other', description TEXT, amount_planned DECIMAL(15,2) DEFAULT 0.00, amount_consumed DECIMAL(15,2) DEFAULT 0.00, is_deleted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
"""

# ---------------------------------------------------------------------------
# Field allowlists — only these columns may appear in INSERT/UPDATE payloads.
# ---------------------------------------------------------------------------
ALLOWED_FIELDS = {
    "projects": {
        "title", "description", "status", "health", "start_date", "end_date",
        "budget_planned", "budget_consumed", "dependency_ids", "created_by",
    },
    "people": {
        "name", "email", "title", "weekly_hours_capacity", "hourly_pay", "is_active",
    },
    "assignments": {
        "person_id", "project_id", "role_on_project", "hours_per_week",
        "start_date", "end_date",
    },
    "deliverables": {
        "project_id", "title", "description", "status", "due_date", "depends_on_id",
    },
    "budget_items": {
        "project_id", "category", "description", "amount_planned", "amount_consumed",
    },
}

# Valid enum values
VALID_STATUSES = {"projects": {"active", "inactive", "on_hold", "completed", "cancelled"}}
VALID_DELIVERABLE_STATUSES = {"pending", "in_progress", "completed", "cancelled"}
VALID_HEALTH = {"green", "amber", "red"}
VALID_BUDGET_CATEGORIES = {"staff", "tooling", "infrastructure", "travel", "other"}


def filter_fields(table: str, body: dict) -> dict:
    """Returns only the allowed fields for the given table, stripping unknown keys."""
    allowed = ALLOWED_FIELDS.get(table, set())
    return {k: v for k, v in body.items() if k in allowed}


def get_db():
    """Returns a reused PostgreSQL connection, reconnecting if closed or broken."""
    global _conn
    try:
        if _conn is not None and not _conn.closed:
            # Lightweight health check — catches stale connections.
            _conn.execute("SELECT 1")
            return _conn
    except Exception:
        _conn = None

    dsn = (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_NAME', 'postgres')} "
        f"user={os.getenv('POSTGRES_USER', 'postgres')} "
        f"password={os.getenv('POSTGRES_PASS', 'postgres123')} "
        f"connect_timeout=30"
        + ("" if IS_LOCAL else " sslmode=require")
    )
    _conn = psycopg.connect(dsn)
    return _conn


def resp(status: int, body: dict) -> dict:
    """Builds a Lambda HTTP response with CORS headers."""
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": CORS_ORIGIN,
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(body, default=str),
    }


def get_user(event: dict):
    """Returns JWT payload if authenticated, or mock admin in local dev."""
    if IS_LOCAL:
        return {"sub": "00000000-0000-0000-0000-000000000001", "email": "admin@acme.com", "name": "Dev Admin", "role": "admin"}
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


UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def extract_id(path: str):
    """Extracts the first UUID segment from a request path."""
    for segment in path.split("/"):
        if UUID_RE.match(segment):
            return segment
    return None


def rows_to_dicts(cursor) -> list:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def row_to_dict(cursor, row) -> dict:
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


def init_db():
    """Creates all tables idempotently. Safe to call on every cold start."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()


def hash_password(plain: str) -> str:
    import hashlib, os as _os, base64
    salt = _os.urandom(16)
    # 200K iterations is intentionally slow for prod security; use minimal rounds
    # locally so cold-start init_db() doesn't burn seconds on PBKDF2.
    iterations = 1_000 if IS_LOCAL else 200_000
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        import hashlib, base64, hmac
        algo, iter_s, salt_b64, hash_b64 = hashed.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        digest = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, int(iter_s))
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


def calculate_health(data: dict) -> tuple[str, str]:
    """Derives RAG health from dates and budget — worse-of-two.

    Budget: green <70%, amber 70-95%, red >95%.
    Time:   green >5d,  amber 1-5d,  red <=1d (or overdue).
    Missing end_date is treated as plenty of time.
    Returns (color, reason).
    """
    severity = {"green": 0, "amber": 1, "red": 2}

    planned = float(data.get("budget_planned") or 0)
    consumed = float(data.get("budget_consumed") or 0)
    budget_band, budget_reason = "green", ""
    if planned > 0:
        ratio = consumed / planned
        if ratio > 0.95:
            budget_band, budget_reason = "red", "budget above 95%"
        elif ratio >= 0.70:
            budget_band, budget_reason = "amber", "budget above 70%"

    end_date = data.get("end_date")
    time_band, time_reason = "green", ""
    if end_date:
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date[:10])
        days = (end_date - date.today()).days
        if days < 0:
            time_band, time_reason = "red", "overdue"
        elif days <= 1:
            time_band, time_reason = "red", "1 day or less remaining"
        elif days <= 5:
            time_band, time_reason = "amber", "5 days or less remaining"

    if severity[budget_band] >= severity[time_band]:
        worst = budget_band
    else:
        worst = time_band

    if worst == "green":
        return "green", "On track"
    reasons = [r for r in (budget_reason, time_reason) if r]
    return worst, "; ".join(reasons)

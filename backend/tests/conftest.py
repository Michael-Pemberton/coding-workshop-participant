"""Shared fixtures and helpers for Lambda handler tests.

Tests run from the backend/ directory:
    cd backend && IS_LOCAL=true pytest tests/ -v
"""

import importlib.util
import json
import os
import shutil
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("IS_LOCAL", "true")
os.environ.setdefault("JWT_SECRET", "test-secret")

# psycopg / jwt / requests are vendored inside each Lambda folder. Put one of
# them on sys.path so they import from the test process itself (needed by the
# integration fixture before any handler is loaded).
for _vendor in ("projects", "auth"):
    _p = os.path.join(BACKEND, _vendor)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)


def load_handler(service: str):
    """Loads a Lambda function.py as a uniquely-named module.

    Copies shared.py into the service directory first so the import works.
    """
    svc_dir = os.path.join(BACKEND, service)
    shared_src = os.path.join(BACKEND, "shared.py")
    shared_dst = os.path.join(svc_dir, "shared.py")
    if os.path.exists(shared_src):
        shutil.copy(shared_src, shared_dst)

    if svc_dir not in sys.path:
        sys.path.insert(0, svc_dir)

    mod_name = f"handler_{service}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]

    fn_path = os.path.join(svc_dir, "function.py")
    spec = importlib.util.spec_from_file_location(mod_name, fn_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def make_event(method: str, path: str, body=None, params=None) -> dict:
    """Builds a minimal Lambda event dict."""
    event = {
        "requestContext": {"http": {"method": method}},
        "rawPath": path,
        "queryStringParameters": params or {},
    }
    if body is not None:
        event["body"] = json.dumps(body)
    return event


@pytest.fixture
def mock_conn(mocker):
    """A MagicMock psycopg connection whose cursor acts as a context manager."""
    conn = mocker.MagicMock()
    cur = mocker.MagicMock()
    cur.description = []
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    cur.rowcount = 1
    conn.cursor.return_value.__enter__ = mocker.MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = mocker.MagicMock(return_value=False)
    conn._cur = cur
    return conn


# ---------------------------------------------------------------------------
# Integration test support — real Postgres connection, transaction per test.
# Skipped automatically if Postgres isn't reachable.
# ---------------------------------------------------------------------------

def _pg_dsn() -> str:
    return (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_NAME', 'postgres')} "
        f"user={os.getenv('POSTGRES_USER', 'postgres')} "
        f"password={os.getenv('POSTGRES_PASS', 'postgres123')} "
        f"connect_timeout=2"
    )


def _postgres_available() -> bool:
    try:
        import psycopg
        with psycopg.connect(_pg_dsn()) as c:
            c.execute("SELECT 1")
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def _pg_ok():
    if not _postgres_available():
        pytest.skip("Postgres not reachable on localhost:5432 — skipping integration tests")
    return True


@pytest.fixture
def integration_db(_pg_ok):
    """A real psycopg connection wrapped in a transaction that is rolled back
    after the test. Handlers committing on this connection are neutralized so
    rollback still cleans everything up.
    """
    import psycopg
    conn = psycopg.connect(_pg_dsn())
    conn.autocommit = False
    # Make handler-level conn.commit() a no-op by issuing a SAVEPOINT we never
    # release — psycopg's commit() will still try to COMMIT, so instead we
    # monkey-patch the method directly on this instance.
    conn.commit = lambda: None  # type: ignore[method-assign]
    try:
        yield conn
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def integration_handler(service: str, mocker, conn):
    """Loads a Lambda handler and patches it to use the integration_db connection."""
    mod = load_handler(service)
    mocker.patch.object(mod, "get_db", return_value=conn)
    return mod

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

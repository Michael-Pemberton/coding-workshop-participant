"""JWT authentication and RBAC middleware for Lambda handlers."""
import logging
import os
from typing import Optional

import jwt

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "")
IS_LOCAL = os.getenv("IS_LOCAL", "false") == "true"

if not IS_LOCAL and not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable must be set in production.")
if not JWT_SECRET:
    JWT_SECRET = "dev-secret-key-change-in-production"


def validate_token(event: dict) -> Optional[dict]:
    """
    Extracts and validates a JWT from the Authorization header.

    Args:
        event: Lambda event dict containing headers.

    Returns:
        dict: Decoded JWT payload if valid, None otherwise.
    """
    headers = event.get("headers") or {}
    auth_header = headers.get("authorization") or headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning("Invalid JWT token: %s", exc)
        return None


def require_auth(event: dict) -> dict:
    """
    Validates the JWT and returns the user payload.
    In local dev mode returns a mock admin without checking the token.

    Args:
        event: Lambda event dict.

    Returns:
        dict: Decoded JWT payload with user information.

    Raises:
        PermissionError: If the token is missing or invalid.
    """
    if IS_LOCAL:
        return {"sub": "dev-user", "email": "admin@acme.com", "name": "Dev Admin", "role": "admin"}
    user = validate_token(event)
    if not user:
        raise PermissionError("Authentication required")
    return user


def require_role(event: dict, required_roles: list[str]) -> dict:
    """
    Validates the JWT and asserts the user has one of the required roles.

    Args:
        event: Lambda event dict.
        required_roles: List of role strings that are permitted.

    Returns:
        dict: Decoded JWT payload if authorized.

    Raises:
        PermissionError: If unauthenticated or role is insufficient.
    """
    user = require_auth(event)
    if user.get("role") not in required_roles:
        raise PermissionError(f"Access denied. Required roles: {required_roles}")
    return user

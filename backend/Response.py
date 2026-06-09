"""Standardized HTTP response helpers for Lambda functions."""
import json
from typing import Any


def cors_headers() -> dict:
    """Returns CORS headers required for all responses."""
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Methods": "*",
    }


def success(data: Any, status_code: int = 200) -> dict:
    """
    Builds a successful Lambda HTTP response.

    Args:
        data: The response payload.
        status_code: HTTP status code (default 200).

    Returns:
        dict: Lambda-compatible response with statusCode, headers, and body.
    """
    return {
        "statusCode": status_code,
        "headers": cors_headers(),
        "body": json.dumps({"data": data, "success": True}, default=str),
    }


def error(message: str, status_code: int = 400) -> dict:
    """
    Builds an error Lambda HTTP response.

    Args:
        message: Human-readable error description.
        status_code: HTTP status code (default 400).

    Returns:
        dict: Lambda-compatible response with statusCode, headers, and body.
    """
    return {
        "statusCode": status_code,
        "headers": cors_headers(),
        "body": json.dumps({"error": message, "success": False}),
    }


def no_content() -> dict:
    """Returns a 204 No Content response (used for deletions and CORS preflight)."""
    return {"statusCode": 204, "headers": cors_headers(), "body": ""}

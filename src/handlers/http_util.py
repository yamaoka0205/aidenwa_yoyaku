"""Shared helpers for HTTP (API Gateway / Function URL) handlers."""

from __future__ import annotations

import base64
import json
from typing import Any


def parse_body(event: dict[str, Any] | None) -> dict[str, Any]:
    if not event:
        return {}
    if "body" in event:
        body = event["body"]
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")
        if isinstance(body, str):
            return json.loads(body or "{}")
        return body or {}
    return event


def response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "content-type,authorization",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(payload, ensure_ascii=False),
    }

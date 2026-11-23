"""Lambda: admin login via Cognito USER_PASSWORD_AUTH."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from booking.auth import login_with_password
from handlers.http_util import parse_body, response


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
    try:
        if (event or {}).get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
            return response(204, {})
        data = parse_body(event)
        result = login_with_password(
            email=str(data.get("email") or ""),
            password=str(data.get("password") or ""),
        )
        status = result.get("status")
        http = 200
        if status == "invalid_request":
            http = 400
        elif status == "unauthorized":
            http = 401
        elif status == "forbidden":
            http = 403
        elif status == "challenge":
            http = 409
        elif status == "error":
            http = 500
        return response(http, result)
    except Exception as exc:  # noqa: BLE001
        return response(500, {"status": "error", "reason": str(exc)})

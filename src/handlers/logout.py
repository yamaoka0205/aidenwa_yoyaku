"""Lambda: Cognito GlobalSignOut for the access token."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from booking.auth import bearer_token, logout_access_token
from handlers.http_util import response


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
    try:
        token = bearer_token(event) or ""
        result = logout_access_token(token)
        return response(200, result)
    except Exception as exc:  # noqa: BLE001
        return response(500, {"status": "error", "reason": str(exc)})

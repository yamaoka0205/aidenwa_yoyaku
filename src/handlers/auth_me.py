"""Lambda: return current admin session from Cognito access token."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from booking.auth import require_session, session_payload
from booking.db import BookingStore
from handlers.http_util import response


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
    try:
        store = BookingStore()
        auth = require_session(store, event)
        if not auth["ok"]:
            return response(auth["status_code"], auth["body"])
        return response(200, session_payload(auth["session"]))
    except Exception as exc:  # noqa: BLE001
        return response(500, {"status": "error", "reason": str(exc)})

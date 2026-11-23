"""Operator: list store applications."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from booking.applications import list_applications
from booking.auth import require_operator
from booking.db import BookingStore
from handlers.http_util import parse_body, response


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
    try:
        store = BookingStore()
        auth = require_operator(store, event)
        if not auth["ok"]:
            return response(auth["status_code"], auth["body"])
        data = parse_body(event)
        status = str(data.get("status") or "pending")
        result = list_applications(store, status=status)
        return response(200, result)
    except Exception as exc:  # noqa: BLE001
        return response(500, {"status": "error", "reason": str(exc)})

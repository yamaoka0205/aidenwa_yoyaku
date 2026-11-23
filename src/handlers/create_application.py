"""Public: store self-application."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from booking.applications import create_application
from booking.db import BookingStore
from handlers.http_util import parse_body, response


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
    try:
        data = parse_body(event)
        result = create_application(
            BookingStore(),
            store_name=str(data.get("storeName") or ""),
            contact_name=str(data.get("contactName") or ""),
            contact_email=str(data.get("contactEmail") or ""),
            contact_phone=str(data.get("contactPhone") or ""),
            note=str(data.get("note") or ""),
        )
        http = 200 if result.get("status") == "ok" else 400
        return response(http, result)
    except Exception as exc:  # noqa: BLE001
        return response(500, {"status": "error", "reason": str(exc)})

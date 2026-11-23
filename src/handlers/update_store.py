"""Lambda handler: update store settings (auth required)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from booking.auth import require_session
from booking.db import BookingStore
from booking.store_view import update_store
from handlers.http_util import parse_body, response


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
    try:
        store = BookingStore()
        auth = require_session(store, event)
        if not auth["ok"]:
            return response(auth["status_code"], auth["body"])

        data = parse_body(event)
        tenant_id = str(auth["session"].get("tenantId"))
        result = update_store(
            store,
            tenant_id=tenant_id,
            name=data.get("name"),
            standard_duration_min=data.get("standardDurationMin"),
            hours=data.get("hours"),
            faqs=data.get("faqs"),
        )
        http = 200
        if result.get("status") == "not_found":
            http = 404
        elif result.get("status") == "invalid_request":
            http = 400
        return response(http, result)
    except Exception as exc:  # noqa: BLE001
        return response(500, {"status": "error", "reason": str(exc)})

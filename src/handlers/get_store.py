"""Lambda handler: get store settings (auth required)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from booking.auth import require_session
from booking.db import BookingStore
from booking.store_view import get_store
from handlers.http_util import response


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
    try:
        store = BookingStore()
        auth = require_session(store, event)
        if not auth["ok"]:
            return response(auth["status_code"], auth["body"])
        tenant_id = str(auth["session"].get("tenantId"))
        result = get_store(store, tenant_id)
        http = 200 if result.get("status") == "ok" else 404
        return response(http, result)
    except Exception as exc:  # noqa: BLE001
        return response(500, {"status": "error", "reason": str(exc)})

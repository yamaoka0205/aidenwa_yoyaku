"""Lambda handler: confirm a reservation (auth required for HTTP)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from booking.auth import require_session
from booking.confirm import confirm_reservation
from booking.db import BookingStore
from handlers.http_util import parse_body, response


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
    try:
        store = BookingStore()
        is_http = bool((event or {}).get("requestContext") or (event or {}).get("headers"))
        data = parse_body(event)
        if is_http:
            auth = require_session(store, event)
            if not auth["ok"]:
                return response(auth["status_code"], auth["body"])
            tenant_id = str(auth["session"].get("tenantId"))
            source = str(data.get("source") or "manual")
        else:
            tenant_id = data.get("tenantId")
            source = str(data.get("source") or "manual")

        date_s = data.get("date")
        start_time = data.get("startTime")
        party_size = data.get("partySize")
        customer_name = data.get("customerName")

        missing = [
            name
            for name, value in (
                ("tenantId", tenant_id),
                ("date", date_s),
                ("startTime", start_time),
                ("partySize", party_size),
                ("customerName", customer_name),
            )
            if value is None or value == ""
        ]
        if missing:
            return response(
                400,
                {"status": "invalid_request", "reason": "missing_fields", "fields": missing},
            )

        try:
            party_size_i = int(party_size)
        except (TypeError, ValueError):
            return response(400, {"status": "invalid_request", "reason": "invalid_party_size"})

        result = confirm_reservation(
            store,
            tenant_id=str(tenant_id),
            date_s=str(date_s),
            start_time_s=str(start_time),
            party_size=party_size_i,
            customer_name=str(customer_name),
            customer_phone=data.get("customerPhone"),
            source=source,
            call_id=data.get("callId"),
            preferred_table_id=data.get("tableId"),
        )
        payload = result.to_dict()
        http = 200
        if result.status == "confirmed":
            http = 201
        elif result.status in {"invalid_request", "invalid_slot"}:
            http = 400
        elif result.status == "not_found":
            http = 404
        elif result.status == "full":
            http = 409
        return response(http, payload)
    except Exception as exc:  # noqa: BLE001
        return response(500, {"status": "error", "reason": str(exc)})

"""Operator: approve or reject a store application."""

from __future__ import annotations

import secrets
import string
import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from booking.applications import get_application, review_application
from booking.auth import provision_store_user, require_operator
from booking.db import BookingStore
from handlers.http_util import parse_body, response


def _temp_password() -> str:
    # Cognito policy: upper, lower, number, symbol, min 8
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(10))
    return f"Tmp-{core}!"


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
    try:
        store = BookingStore()
        auth = require_operator(store, event)
        if not auth["ok"]:
            return response(auth["status_code"], auth["body"])

        data = parse_body(event)
        application_id = str(data.get("applicationId") or "")
        decision = str(data.get("decision") or "")
        if not application_id or not decision:
            return response(
                400,
                {
                    "status": "invalid_request",
                    "reason": "missing_fields",
                    "fields": [
                        n
                        for n, v in (
                            ("applicationId", application_id),
                            ("decision", decision),
                        )
                        if not v
                    ],
                },
            )

        provision = None
        if decision.strip().lower() == "approve":
            item = get_application(store, application_id)
            if not item:
                return response(404, {"status": "not_found", "reason": "application_not_found"})
            if item.get("status") != "pending":
                return response(
                    409,
                    {"status": "conflict", "reason": "already_reviewed"},
                )
            password = _temp_password()
            created = provision_store_user(
                email=str(item.get("contactEmail") or ""),
                name=str(item.get("contactName") or ""),
                temporary_password=password,
            )
            if created.get("status") != "ok":
                return response(500, created)
            provision = {
                "userId": created["userId"],
                "temporaryPassword": created["temporaryPassword"],
            }

        result = review_application(
            store,
            application_id=application_id,
            decision=decision,
            reviewer_user_id=str(auth["session"].get("userId") or ""),
            reject_reason=str(data.get("rejectReason") or ""),
            provision_user=provision,
        )
        http = 200
        if result.get("status") == "not_found":
            http = 404
        elif result.get("status") == "conflict":
            http = 409
        elif result.get("status") == "invalid_request":
            http = 400
        return response(http, result)
    except Exception as exc:  # noqa: BLE001
        return response(500, {"status": "error", "reason": str(exc)})

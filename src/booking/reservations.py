"""List reservations for the admin UI."""

from __future__ import annotations

from typing import Any

from booking.db import BookingStore


def _public_reservation(item: dict) -> dict[str, Any]:
    return {
        "reservationId": item.get("reservationId"),
        "date": item.get("date"),
        "startTime": item.get("startTime"),
        "endTime": item.get("endTime"),
        "partySize": int(item.get("partySize", 0)),
        "customerName": item.get("customerName", ""),
        "customerPhone": item.get("customerPhone") or "",
        "tableId": item.get("tableId"),
        "status": item.get("status", "confirmed"),
        "source": item.get("source", "manual"),
        "note": item.get("note") or "",
        "createdAt": item.get("createdAt"),
    }


def list_reservations(
    store: BookingStore, *, tenant_id: str, date_s: str
) -> dict[str, Any]:
    profile = store.get_profile(tenant_id)
    if not profile or profile.get("status") != "active":
        return {
            "status": "not_found",
            "tenantId": tenant_id,
            "date": date_s,
            "reason": "tenant_not_found",
        }

    items = store.list_reservations_for_date(tenant_id, date_s)
    reservations = [_public_reservation(i) for i in items]
    # Hide cancelled for MVP list; keep in payload if needed later.
    active = [r for r in reservations if r.get("status") != "cancelled"]
    active.sort(key=lambda r: (r.get("startTime") or "", r.get("reservationId") or ""))

    party_total = sum(int(r.get("partySize") or 0) for r in active)
    return {
        "status": "ok",
        "tenantId": tenant_id,
        "date": date_s,
        "count": len(active),
        "partyTotal": party_total,
        "reservations": active,
    }

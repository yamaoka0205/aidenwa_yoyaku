"""Read / update store settings for the admin UI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from booking.db import BookingStore
from booking.faq import list_faqs
from booking.timeutil import DOW_KEYS


DOW_LABELS = {
    "mon": "月",
    "tue": "火",
    "wed": "水",
    "thu": "木",
    "fri": "金",
    "sat": "土",
    "sun": "日",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _public_table(item: dict) -> dict[str, Any]:
    return {
        "tableId": item.get("tableId"),
        "label": item.get("label"),
        "capacity": int(item.get("capacity", 0)),
        "aiBookable": bool(item.get("aiBookable")),
        "active": bool(item.get("active", True)),
        "sortOrder": int(item.get("sortOrder", 0)),
    }


def _public_faq(item: dict) -> dict[str, Any]:
    faq_id = str(item.get("SK", "")).removeprefix("FAQ#")
    return {
        "faqId": faq_id,
        "question": item.get("question", ""),
        "answer": item.get("answer", ""),
        "tags": list(item.get("tags") or []),
        "enabled": bool(item.get("enabled", True)),
        "sortOrder": int(item.get("sortOrder", 0)),
    }


def _public_hours(item: dict) -> dict[str, Any]:
    dow = str(item.get("SK", "")).removeprefix("HOURS#")
    return {
        "dow": dow,
        "label": DOW_LABELS.get(dow, dow),
        "openTime": item.get("openTime", "11:00"),
        "closeTime": item.get("closeTime", "22:00"),
        "lastStartTime": item.get("lastStartTime"),
        "isClosed": bool(item.get("isClosed", False)),
    }


def get_store(store: BookingStore, tenant_id: str) -> dict[str, Any]:
    profile = store.get_profile(tenant_id)
    if not profile:
        return {"status": "not_found", "tenantId": tenant_id, "reason": "tenant_not_found"}

    hours_raw = store.list_hours(tenant_id)
    hours_by_dow = {_public_hours(h)["dow"]: _public_hours(h) for h in hours_raw}
    hours = [hours_by_dow.get(d) or {"dow": d, "label": DOW_LABELS[d], "isClosed": True} for d in DOW_KEYS]

    tables = sorted(
        (_public_table(t) for t in store.list_tables(tenant_id)),
        key=lambda t: (t["sortOrder"], t["tableId"] or ""),
    )
    faqs = sorted(
        (_public_faq(f) for f in list_faqs(store, tenant_id)),
        key=lambda f: (f["sortOrder"], f["faqId"]),
    )

    return {
        "status": "ok",
        "tenantId": tenant_id,
        "name": profile.get("name", ""),
        "timezone": profile.get("timezone", "Asia/Tokyo"),
        "standardDurationMin": int(profile.get("standardDurationMin", 120)),
        "reservationSlotMin": int(profile.get("reservationSlotMin", 15)),
        "inboundId": profile.get("inboundId", ""),
        "transferPhoneNumber": profile.get("transferPhoneNumber", ""),
        "hours": hours,
        "tables": tables,
        "faqs": faqs,
    }


def update_store(
    store: BookingStore,
    *,
    tenant_id: str,
    name: str | None = None,
    standard_duration_min: int | None = None,
    hours: list[dict] | None = None,
    faqs: list[dict] | None = None,
) -> dict[str, Any]:
    profile = store.get_profile(tenant_id)
    if not profile:
        return {"status": "not_found", "tenantId": tenant_id, "reason": "tenant_not_found"}

    now = _utc_now_iso()
    if name is not None:
        profile["name"] = str(name).strip() or profile.get("name", "")
    if standard_duration_min is not None:
        duration = int(standard_duration_min)
        if duration not in {60, 90, 120, 150, 180}:
            return {
                "status": "invalid_request",
                "tenantId": tenant_id,
                "reason": "invalid_duration",
            }
        profile["standardDurationMin"] = duration
    profile["updatedAt"] = now
    store.put_item(profile)

    if hours is not None:
        duration = int(profile.get("standardDurationMin", 120))
        for row in hours:
            dow = str(row.get("dow", ""))
            if dow not in DOW_KEYS:
                continue
            is_closed = bool(row.get("isClosed", False))
            open_time = str(row.get("openTime") or "11:00")
            close_time = str(row.get("closeTime") or "22:00")
            last_start = _last_start_time(close_time, duration) if not is_closed else None
            item = {
                "PK": f"TENANT#{tenant_id}",
                "SK": f"HOURS#{dow}",
                "entityType": "HOURS",
                "tenantId": tenant_id,
                "openTime": open_time,
                "closeTime": close_time,
                "isClosed": is_closed,
                "updatedAt": now,
            }
            if last_start:
                item["lastStartTime"] = last_start
            store.put_item(item)

    if faqs is not None:
        # Replace FAQ set: write provided items; disable missing ones.
        existing = {str(f.get("SK", "")).removeprefix("FAQ#"): f for f in list_faqs(store, tenant_id)}
        seen: set[str] = set()
        for idx, row in enumerate(faqs):
            faq_id = str(row.get("faqId") or f"f{idx + 1:03d}").strip()
            if not faq_id:
                continue
            seen.add(faq_id)
            store.put_item(
                {
                    "PK": f"TENANT#{tenant_id}",
                    "SK": f"FAQ#{faq_id}",
                    "entityType": "FAQ",
                    "tenantId": tenant_id,
                    "question": str(row.get("question") or "").strip(),
                    "answer": str(row.get("answer") or "").strip(),
                    "tags": list(row.get("tags") or []),
                    "enabled": bool(row.get("enabled", True)),
                    "sortOrder": int(row.get("sortOrder", idx + 1)),
                    "updatedAt": now,
                }
            )
        for faq_id, old in existing.items():
            if faq_id not in seen:
                old = dict(old)
                old["enabled"] = False
                old["updatedAt"] = now
                store.put_item(old)

    return get_store(store, tenant_id)


def _last_start_time(close_time: str, duration_min: int) -> str:
    h, m = map(int, close_time.split(":"))
    total = h * 60 + m - duration_min
    if total < 0:
        return "00:00"
    return f"{total // 60:02d}:{total % 60:02d}"

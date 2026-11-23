"""Store self-application + operator review."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from booking.db import BookingStore
from booking.ids import new_reservation_id
from booking.timeutil import DOW_KEYS


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_application_id() -> str:
    # time-sortable-ish id without extra deps
    return new_reservation_id()


def _new_tenant_id() -> str:
    return f"t_{secrets.token_hex(4)}"


def create_application(
    store: BookingStore,
    *,
    store_name: str,
    contact_name: str,
    contact_email: str,
    contact_phone: str = "",
    note: str = "",
) -> dict[str, Any]:
    store_name = (store_name or "").strip()
    contact_name = (contact_name or "").strip()
    contact_email = (contact_email or "").strip().lower()
    contact_phone = (contact_phone or "").strip()
    note = (note or "").strip()

    missing = [
        n
        for n, v in (
            ("storeName", store_name),
            ("contactName", contact_name),
            ("contactEmail", contact_email),
        )
        if not v
    ]
    if missing:
        return {"status": "invalid_request", "reason": "missing_fields", "fields": missing}
    if "@" not in contact_email:
        return {"status": "invalid_request", "reason": "invalid_email"}

    now = _utc_now_iso()
    application_id = _new_application_id()
    item = {
        "PK": "APP",
        "SK": f"APPLICATION#{application_id}",
        "entityType": "TENANT_APPLICATION",
        "applicationId": application_id,
        "status": "pending",
        "storeName": store_name,
        "contactName": contact_name,
        "contactEmail": contact_email,
        "contactPhone": contact_phone,
        "note": note,
        "createdAt": now,
        "updatedAt": now,
        # Keep GSI2 attrs ready even if index is not enabled yet.
        "GSI2PK": "APPLICATION#pending",
        "GSI2SK": f"{now}#{application_id}",
    }
    store.put_item(item)
    return {
        "status": "ok",
        "applicationId": application_id,
        "message": "申し込みを受け付けました。運営者の承認後にログインできます。",
    }


def _public_application(item: dict) -> dict[str, Any]:
    return {
        "applicationId": item.get("applicationId"),
        "status": item.get("status"),
        "storeName": item.get("storeName"),
        "contactName": item.get("contactName"),
        "contactEmail": item.get("contactEmail"),
        "contactPhone": item.get("contactPhone") or "",
        "note": item.get("note") or "",
        "createdAt": item.get("createdAt"),
        "reviewedAt": item.get("reviewedAt"),
        "reviewedByUserId": item.get("reviewedByUserId"),
        "tenantId": item.get("tenantId"),
        "rejectReason": item.get("rejectReason") or "",
    }


def list_applications(
    store: BookingStore, *, status: str | None = "pending"
) -> dict[str, Any]:
    from boto3.dynamodb.conditions import Key

    items: list[dict] = []
    kwargs = {
        "KeyConditionExpression": Key("PK").eq("APP")
        & Key("SK").begins_with("APPLICATION#")
    }
    while True:
        resp = store.table.query(**kwargs)
        items.extend(resp.get("Items", []))
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        kwargs["ExclusiveStartKey"] = last

    if status and status != "all":
        items = [i for i in items if i.get("status") == status]

    items.sort(key=lambda i: i.get("createdAt") or "", reverse=True)
    return {
        "status": "ok",
        "count": len(items),
        "applications": [_public_application(i) for i in items],
    }


def get_application(store: BookingStore, application_id: str) -> dict | None:
    return store.table.get_item(
        Key={"PK": "APP", "SK": f"APPLICATION#{application_id}"}
    ).get("Item")


def _seed_tenant_basics(store: BookingStore, *, tenant_id: str, store_name: str, now: str) -> None:
    store.put_item(
        {
            "PK": f"TENANT#{tenant_id}",
            "SK": "PROFILE",
            "entityType": "TENANT_PROFILE",
            "tenantId": tenant_id,
            "name": store_name,
            "status": "active",
            "standardDurationMin": 120,
            "reservationSlotMin": 15,
            "timezone": "Asia/Tokyo",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    for dow in DOW_KEYS:
        closed = dow == "sun"
        store.put_item(
            {
                "PK": f"TENANT#{tenant_id}",
                "SK": f"HOURS#{dow}",
                "entityType": "HOURS",
                "tenantId": tenant_id,
                "openTime": "11:00",
                "closeTime": "22:00",
                "lastStartTime": "20:00",
                "isClosed": closed,
                "updatedAt": now,
            }
        )
    tables = [
        ("T4-01", 4, "4人用A", True, 1),
        ("T4-02", 4, "4人用B", True, 2),
        ("T4-03", 4, "4人用C", True, 3),
        ("T4-04", 4, "4人用D", True, 4),
        ("T6-01", 6, "6人用A", True, 5),
        ("T6-02", 6, "6人用B", True, 6),
        ("T4-05", 4, "4人用E（当日客用）", False, 7),
        ("T4-06", 4, "4人用F（当日客用）", False, 8),
    ]
    for table_id, capacity, label, ai, order in tables:
        store.put_item(
            {
                "PK": f"TENANT#{tenant_id}",
                "SK": f"TABLE#{table_id}",
                "entityType": "TABLE",
                "tenantId": tenant_id,
                "tableId": table_id,
                "capacity": capacity,
                "label": label,
                "aiBookable": ai,
                "active": True,
                "sortOrder": order,
                "updatedAt": now,
            }
        )


def review_application(
    store: BookingStore,
    *,
    application_id: str,
    decision: str,
    reviewer_user_id: str,
    reject_reason: str = "",
    provision_user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Approve or reject. provision_user is set by handler after Cognito user create."""
    item = get_application(store, application_id)
    if not item:
        return {"status": "not_found", "reason": "application_not_found"}
    if item.get("status") != "pending":
        return {
            "status": "conflict",
            "reason": "already_reviewed",
            "application": _public_application(item),
        }

    now = _utc_now_iso()
    decision = (decision or "").strip().lower()
    if decision == "reject":
        item["status"] = "rejected"
        item["rejectReason"] = (reject_reason or "").strip()
        item["reviewedAt"] = now
        item["reviewedByUserId"] = reviewer_user_id
        item["updatedAt"] = now
        item["GSI2PK"] = "APPLICATION#rejected"
        item["GSI2SK"] = f"{now}#{application_id}"
        store.put_item(item)
        return {"status": "ok", "application": _public_application(item)}

    if decision != "approve":
        return {"status": "invalid_request", "reason": "invalid_decision"}

    tenant_id = _new_tenant_id()
    store_name = str(item.get("storeName") or "新しい店舗")
    _seed_tenant_basics(store, tenant_id=tenant_id, store_name=store_name, now=now)

    user_id = (provision_user or {}).get("userId")
    temp_password = (provision_user or {}).get("temporaryPassword")
    if user_id:
        store.put_item(
            {
                "PK": f"EMAIL#{str(item.get('contactEmail') or '').lower()}",
                "SK": "USER",
                "entityType": "EMAIL_LOOKUP",
                "email": str(item.get("contactEmail") or "").lower(),
                "userId": user_id,
                "updatedAt": now,
            }
        )
        store.put_item(
            {
                "PK": f"USER#{user_id}",
                "SK": f"MEMBERSHIP#{tenant_id}",
                "entityType": "MEMBERSHIP",
                "userId": user_id,
                "tenantId": tenant_id,
                "role": "tenant_admin",
                "status": "active",
                "displayName": str(item.get("contactName") or store_name),
                "updatedAt": now,
            }
        )

    item["status"] = "approved"
    item["tenantId"] = tenant_id
    item["reviewedAt"] = now
    item["reviewedByUserId"] = reviewer_user_id
    item["updatedAt"] = now
    item["GSI2PK"] = "APPLICATION#approved"
    item["GSI2SK"] = f"{now}#{application_id}"
    store.put_item(item)

    out = {
        "status": "ok",
        "application": _public_application(item),
        "tenantId": tenant_id,
    }
    if temp_password:
        out["temporaryPassword"] = temp_password
    if user_id:
        out["userId"] = user_id
    return out

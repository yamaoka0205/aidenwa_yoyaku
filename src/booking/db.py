"""DynamoDB access helpers for BookingApp."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key


def _aws_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    if region:
        kwargs["region_name"] = region
    endpoint = os.environ.get("DYNAMODB_ENDPOINT_URL")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
        kwargs["aws_access_key_id"] = os.environ.get("AWS_ACCESS_KEY_ID", "local")
        kwargs["aws_secret_access_key"] = os.environ.get(
            "AWS_SECRET_ACCESS_KEY", "local"
        )
    return kwargs


def _resource():
    return boto3.resource("dynamodb", **_aws_kwargs())


def _client():
    # Low-level client for TransactWriteItems (avoid resource re-serialization).
    return boto3.client("dynamodb", **_aws_kwargs())


def to_attr_map(item: dict) -> dict:
    from boto3.dynamodb.types import TypeSerializer

    serializer = TypeSerializer()
    return {k: serializer.serialize(v) for k, v in item.items()}


class BookingStore:
    def __init__(self, table_name: str | None = None):
        self.table_name = table_name or os.environ.get("BOOKING_TABLE_NAME", "BookingApp")
        self.table = _resource().Table(self.table_name)
        self.client = _client()

    def get_inbound(self, inbound_id: str) -> dict | None:
        return self.table.get_item(
            Key={"PK": f"INBOUND#{inbound_id}", "SK": "TENANT"}
        ).get("Item")

    def get_profile(self, tenant_id: str) -> dict | None:
        return self.table.get_item(
            Key={"PK": f"TENANT#{tenant_id}", "SK": "PROFILE"}
        ).get("Item")

    def get_hours(self, tenant_id: str, dow: str) -> dict | None:
        return self.table.get_item(
            Key={"PK": f"TENANT#{tenant_id}", "SK": f"HOURS#{dow}"}
        ).get("Item")

    def list_tables(self, tenant_id: str) -> list[dict]:
        items: list[dict] = []
        kwargs = {
            "KeyConditionExpression": Key("PK").eq(f"TENANT#{tenant_id}")
            & Key("SK").begins_with("TABLE#")
        }
        while True:
            resp = self.table.query(**kwargs)
            items.extend(resp.get("Items", []))
            last = resp.get("LastEvaluatedKey")
            if not last:
                break
            kwargs["ExclusiveStartKey"] = last
        return items

    def list_hours(self, tenant_id: str) -> list[dict]:
        items: list[dict] = []
        kwargs = {
            "KeyConditionExpression": Key("PK").eq(f"TENANT#{tenant_id}")
            & Key("SK").begins_with("HOURS#")
        }
        while True:
            resp = self.table.query(**kwargs)
            items.extend(resp.get("Items", []))
            last = resp.get("LastEvaluatedKey")
            if not last:
                break
            kwargs["ExclusiveStartKey"] = last
        return items

    def list_reservations_for_date(self, tenant_id: str, date_s: str) -> list[dict]:
        """A4: reservations for one day, SK begins_with RES#DATE#yyyy-mm-dd."""
        prefix = f"RES#DATE#{date_s}"
        items: list[dict] = []
        kwargs = {
            "KeyConditionExpression": Key("PK").eq(f"TENANT#{tenant_id}")
            & Key("SK").begins_with(prefix)
        }
        while True:
            resp = self.table.query(**kwargs)
            items.extend(resp.get("Items", []))
            last = resp.get("LastEvaluatedKey")
            if not last:
                break
            kwargs["ExclusiveStartKey"] = last
        return items

    def put_item(self, item: dict) -> None:
        self.table.put_item(Item=item)

    def get_slot(
        self, tenant_id: str, table_id: str, date_s: str, time_key: str
    ) -> dict | None:
        sk = f"SLOT#TABLE#{table_id}#DATE#{date_s}#TIME#{time_key}"
        return self.table.get_item(
            Key={"PK": f"TENANT#{tenant_id}", "SK": sk}
        ).get("Item")


def slot_is_occupied(slot: dict | None, now: datetime | None = None) -> bool:
    """True if the slot blocks a new booking.

    Expired held slots (expiresAt < now) are treated as free.
    """
    if not slot:
        return False
    status = slot.get("status", "confirmed")
    if status == "held":
        expires_at = slot.get("expiresAt")
        if expires_at is None:
            return True
        now = now or datetime.now(timezone.utc)
        # expiresAt is epoch seconds
        return int(expires_at) > int(now.timestamp())
    return True

#!/usr/bin/env python3
"""Seed MEMBERSHIP for the Cognito demo admin user.

Requires build/cognito.json from scripts/setup_cognito_admin.py
(or env COGNITO_DEMO_SUB / DEMO_ADMIN_EMAIL).

Usage:
  python3 scripts/setup_cognito_admin.py
  python3 scripts/seed_demo_admin.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
COGNITO_JSON = ROOT / "build" / "cognito.json"
TABLE_NAME = "BookingApp"
TENANT_ID = "t_demo_001"
DISPLAY_NAME = "さくら店長"
DEFAULT_EMAIL = "demo@sakura.local"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_cognito() -> dict:
    if COGNITO_JSON.exists():
        return json.loads(COGNITO_JSON.read_text())
    return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint-url", default=os.environ.get("DYNAMODB_ENDPOINT_URL"))
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION"),
    )
    args = parser.parse_args()

    cfg = load_cognito()
    user_sub = os.environ.get("COGNITO_DEMO_SUB") or cfg.get("demoUserSub")
    email = (
        os.environ.get("DEMO_ADMIN_EMAIL") or cfg.get("demoEmail") or DEFAULT_EMAIL
    ).strip().lower()
    if not user_sub:
        print(
            "ERROR: missing Cognito sub. Run scripts/setup_cognito_admin.py first.",
            file=sys.stderr,
        )
        return 1

    kwargs: dict = {}
    if args.region:
        kwargs["region_name"] = args.region
    if args.endpoint_url:
        kwargs["endpoint_url"] = args.endpoint_url
        kwargs["aws_access_key_id"] = os.environ.get("AWS_ACCESS_KEY_ID", "local")
        kwargs["aws_secret_access_key"] = os.environ.get("AWS_SECRET_ACCESS_KEY", "local")

    table = boto3.resource("dynamodb", **kwargs).Table(TABLE_NAME)
    now = utc_now_iso()
    items = [
        {
            "PK": f"EMAIL#{email}",
            "SK": "USER",
            "entityType": "EMAIL_LOOKUP",
            "email": email,
            "userId": user_sub,
            "updatedAt": now,
        },
        {
            "PK": f"USER#{user_sub}",
            "SK": f"MEMBERSHIP#{TENANT_ID}",
            "entityType": "MEMBERSHIP",
            "userId": user_sub,
            "tenantId": TENANT_ID,
            "role": "tenant_admin",
            "status": "active",
            "displayName": DISPLAY_NAME,
            "updatedAt": now,
        },
    ]
    for item in items:
        table.put_item(Item=item)
        print(f"Upserted {item['PK']} / {item['SK']}")

    print(f"Demo admin linked: {email} → tenant {TENANT_ID} (sub={user_sub})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Create Cognito User Pool + app client + demo admin user for the admin UI.

Writes build/cognito.json with pool/client IDs (gitignored via build/).

Demo user:
  email:    demo@sakura.local
  password: Demo-pass-2026!

Usage:
  python3 scripts/setup_cognito_admin.py
  python3 scripts/seed_demo_admin.py   # MEMBERSHIP for Cognito sub
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "cognito.json"
POOL_NAME = "BookingAppAdmin"
CLIENT_NAME = "BookingAppAdminWeb"
DEMO_EMAIL = os.environ.get("DEMO_ADMIN_EMAIL", "demo@sakura.local")
DEMO_PASSWORD = os.environ.get("DEMO_ADMIN_PASSWORD", "Demo-pass-2026!")
OPERATOR_EMAIL = os.environ.get("DEMO_OPERATOR_EMAIL", "operator@sakura.local")
OPERATOR_PASSWORD = os.environ.get("DEMO_OPERATOR_PASSWORD", "Demo-pass-2026!")
OPERATOR_GROUP = "operators"


def region() -> str:
    value = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    if not value:
        print("ERROR: set AWS_DEFAULT_REGION", file=sys.stderr)
        raise SystemExit(1)
    return value


def find_pool(cognito, name: str) -> str | None:
    token = None
    while True:
        kwargs = {"MaxResults": 60}
        if token:
            kwargs["NextToken"] = token
        resp = cognito.list_user_pools(**kwargs)
        for pool in resp.get("UserPools", []):
            if pool.get("Name") == name:
                return pool["Id"]
        token = resp.get("NextToken")
        if not token:
            return None


def ensure_pool(cognito) -> str:
    existing = find_pool(cognito, POOL_NAME)
    if existing:
        print(f"User pool exists {existing}")
        return existing

    print(f"Creating user pool {POOL_NAME}")
    resp = cognito.create_user_pool(
        PoolName=POOL_NAME,
        Policies={
            "PasswordPolicy": {
                "MinimumLength": 8,
                "RequireUppercase": True,
                "RequireLowercase": True,
                "RequireNumbers": True,
                "RequireSymbols": True,
                "TemporaryPasswordValidityDays": 7,
            }
        },
        AutoVerifiedAttributes=["email"],
        UsernameAttributes=["email"],
        MfaConfiguration="OFF",
        AdminCreateUserConfig={"AllowAdminCreateUserOnly": True},
        Schema=[
            {
                "Name": "email",
                "AttributeDataType": "String",
                "Required": True,
                "Mutable": True,
            }
        ],
    )
    pool_id = resp["UserPool"]["Id"]
    print(f"Created user pool {pool_id}")
    return pool_id


def ensure_client(cognito, pool_id: str) -> str:
    resp = cognito.list_user_pool_clients(UserPoolId=pool_id, MaxResults=60)
    for client in resp.get("UserPoolClients", []):
        if client.get("ClientName") == CLIENT_NAME:
            client_id = client["ClientId"]
            print(f"App client exists {client_id}")
            # Ensure auth flows
            cognito.update_user_pool_client(
                UserPoolId=pool_id,
                ClientId=client_id,
                ExplicitAuthFlows=[
                    "ALLOW_USER_PASSWORD_AUTH",
                    "ALLOW_REFRESH_TOKEN_AUTH",
                    "ALLOW_USER_SRP_AUTH",
                ],
                PreventUserExistenceErrors="ENABLED",
            )
            return client_id

    print(f"Creating app client {CLIENT_NAME}")
    created = cognito.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName=CLIENT_NAME,
        GenerateSecret=False,
        ExplicitAuthFlows=[
            "ALLOW_USER_PASSWORD_AUTH",
            "ALLOW_REFRESH_TOKEN_AUTH",
            "ALLOW_USER_SRP_AUTH",
        ],
        PreventUserExistenceErrors="ENABLED",
        AccessTokenValidity=12,
        IdTokenValidity=12,
        RefreshTokenValidity=30,
        TokenValidityUnits={
            "AccessToken": "hours",
            "IdToken": "hours",
            "RefreshToken": "days",
        },
    )
    client_id = created["UserPoolClient"]["ClientId"]
    print(f"Created app client {client_id}")
    return client_id


def ensure_demo_user(cognito, pool_id: str) -> str:
    """Return Cognito username (email) after ensuring permanent password."""
    try:
        cognito.admin_get_user(UserPoolId=pool_id, Username=DEMO_EMAIL)
        print(f"Demo user exists {DEMO_EMAIL}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "UserNotFoundException":
            raise
        print(f"Creating demo user {DEMO_EMAIL}")
        cognito.admin_create_user(
            UserPoolId=pool_id,
            Username=DEMO_EMAIL,
            UserAttributes=[
                {"Name": "email", "Value": DEMO_EMAIL},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "name", "Value": "さくら店長"},
            ],
            MessageAction="SUPPRESS",
            TemporaryPassword=DEMO_PASSWORD,
        )

    cognito.admin_set_user_password(
        UserPoolId=pool_id,
        Username=DEMO_EMAIL,
        Password=DEMO_PASSWORD,
        Permanent=True,
    )
    print("Demo password set (permanent)")

    user = cognito.admin_get_user(UserPoolId=pool_id, Username=DEMO_EMAIL)
    attrs = {a["Name"]: a["Value"] for a in user.get("UserAttributes", [])}
    sub = attrs.get("sub")
    if not sub:
        raise RuntimeError("Cognito user has no sub")
    print(f"Demo user sub={sub}")
    return sub


def ensure_operator_group(cognito, pool_id: str) -> None:
    try:
        cognito.create_group(
            GroupName=OPERATOR_GROUP,
            UserPoolId=pool_id,
            Description="Platform operators who approve store applications",
        )
        print(f"Created group {OPERATOR_GROUP}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "GroupExistsException":
            raise
        print(f"Group exists {OPERATOR_GROUP}")


def ensure_operator_user(cognito, pool_id: str) -> str:
    try:
        cognito.admin_get_user(UserPoolId=pool_id, Username=OPERATOR_EMAIL)
        print(f"Operator user exists {OPERATOR_EMAIL}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "UserNotFoundException":
            raise
        print(f"Creating operator user {OPERATOR_EMAIL}")
        cognito.admin_create_user(
            UserPoolId=pool_id,
            Username=OPERATOR_EMAIL,
            UserAttributes=[
                {"Name": "email", "Value": OPERATOR_EMAIL},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "name", "Value": "運営者"},
            ],
            MessageAction="SUPPRESS",
            TemporaryPassword=OPERATOR_PASSWORD,
        )

    cognito.admin_set_user_password(
        UserPoolId=pool_id,
        Username=OPERATOR_EMAIL,
        Password=OPERATOR_PASSWORD,
        Permanent=True,
    )
    try:
        cognito.admin_add_user_to_group(
            UserPoolId=pool_id,
            Username=OPERATOR_EMAIL,
            GroupName=OPERATOR_GROUP,
        )
    except ClientError as exc:
        # Already in group is fine
        if exc.response["Error"]["Code"] not in {
            "ResourceNotFoundException",
            "InvalidParameterException",
        }:
            # Cognito has no "already in group" code; re-add is idempotent-ish
            pass
    print("Operator password set; added to operators group")

    user = cognito.admin_get_user(UserPoolId=pool_id, Username=OPERATOR_EMAIL)
    attrs = {a["Name"]: a["Value"] for a in user.get("UserAttributes", [])}
    sub = attrs.get("sub")
    if not sub:
        raise RuntimeError("Operator Cognito user has no sub")
    print(f"Operator user sub={sub}")
    return sub


def main() -> int:
    reg = region()
    cognito = boto3.client("cognito-idp", region_name=reg)
    pool_id = ensure_pool(cognito)
    client_id = ensure_client(cognito, pool_id)
    sub = ensure_demo_user(cognito, pool_id)
    ensure_operator_group(cognito, pool_id)
    operator_sub = ensure_operator_user(cognito, pool_id)

    payload = {
        "region": reg,
        "userPoolId": pool_id,
        "clientId": client_id,
        "demoEmail": DEMO_EMAIL,
        "demoUserSub": sub,
        "operatorEmail": OPERATOR_EMAIL,
        "operatorUserSub": operator_sub,
        "issuer": f"https://cognito-idp.{reg}.amazonaws.com/{pool_id}",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {OUT}")
    print("Next: python3 scripts/seed_demo_admin.py")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClientError as exc:
        print(
            f"ERROR [{exc.response['Error']['Code']}]: {exc.response['Error']['Message']}",
            file=sys.stderr,
        )
        raise SystemExit(1)

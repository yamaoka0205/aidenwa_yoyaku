"""Admin auth via Amazon Cognito Access Token.

- Store staff: Cognito user + DynamoDB MEMBERSHIP → tenantId
- Operators: Cognito group `operators` (no MEMBERSHIP required)
"""

from __future__ import annotations

import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

from booking.db import BookingStore

DEMO_EMAIL = os.environ.get("DEMO_ADMIN_EMAIL", "demo@sakura.local")
OPERATOR_EMAIL = os.environ.get("DEMO_OPERATOR_EMAIL", "operator@sakura.local")
DEFAULT_TENANT_ID = "t_demo_001"
OPERATOR_GROUP = "operators"


def _cognito():
    kwargs: dict[str, Any] = {}
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    if region:
        kwargs["region_name"] = region
    return boto3.client("cognito-idp", **kwargs)


def cognito_config() -> dict[str, str]:
    return {
        "userPoolId": os.environ.get("COGNITO_USER_POOL_ID", ""),
        "clientId": os.environ.get("COGNITO_CLIENT_ID", ""),
        "region": os.environ.get("AWS_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
        or "",
    }


def list_memberships(store: BookingStore, user_id: str) -> list[dict]:
    from boto3.dynamodb.conditions import Key

    items: list[dict] = []
    kwargs = {
        "KeyConditionExpression": Key("PK").eq(f"USER#{user_id}")
        & Key("SK").begins_with("MEMBERSHIP#")
    }
    while True:
        resp = store.table.query(**kwargs)
        items.extend(resp.get("Items", []))
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        kwargs["ExclusiveStartKey"] = last
    return items


def active_membership(store: BookingStore, user_id: str) -> dict | None:
    memberships = [
        m
        for m in list_memberships(store, user_id)
        if m.get("status", "active") == "active"
    ]
    return memberships[0] if memberships else None


def get_user_from_access_token(access_token: str) -> dict[str, Any]:
    resp = _cognito().get_user(AccessToken=access_token)
    attrs = {a["Name"]: a["Value"] for a in resp.get("UserAttributes", [])}
    return {
        "username": resp.get("Username", ""),
        "sub": attrs.get("sub") or resp.get("Username", ""),
        "email": attrs.get("email", ""),
        "name": attrs.get("name", ""),
    }


def user_in_operator_group(username: str) -> bool:
    cfg = cognito_config()
    pool_id = cfg.get("userPoolId") or ""
    if not pool_id or not username:
        return False
    try:
        resp = _cognito().admin_list_groups_for_user(
            UserPoolId=pool_id, Username=username, Limit=20
        )
    except ClientError:
        return False
    return any(g.get("GroupName") == OPERATOR_GROUP for g in resp.get("Groups", []))


def login_with_password(*, email: str, password: str) -> dict[str, Any]:
    cfg = cognito_config()
    if not cfg["clientId"]:
        return {"status": "error", "reason": "cognito_not_configured"}

    email_n = (email or "").strip().lower()
    if not email_n or not password:
        return {"status": "invalid_request", "reason": "missing_credentials"}

    try:
        resp = _cognito().initiate_auth(
            ClientId=cfg["clientId"],
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email_n, "PASSWORD": password},
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in {
            "NotAuthorizedException",
            "UserNotFoundException",
            "InvalidParameterException",
        }:
            return {"status": "unauthorized", "reason": "invalid_credentials"}
        return {"status": "error", "reason": code}

    if resp.get("ChallengeName"):
        return {
            "status": "challenge",
            "reason": resp["ChallengeName"],
            "session": resp.get("Session"),
        }

    result = resp.get("AuthenticationResult") or {}
    access = result.get("AccessToken")
    if not access:
        return {"status": "unauthorized", "reason": "no_access_token"}

    try:
        user = get_user_from_access_token(access)
    except ClientError as exc:
        return {"status": "unauthorized", "reason": exc.response["Error"]["Code"]}

    store = BookingStore()
    is_operator = user_in_operator_group(user.get("username") or email_n)
    membership = active_membership(store, user["sub"])

    if is_operator:
        return {
            "status": "ok",
            "accessToken": access,
            "idToken": result.get("IdToken"),
            "refreshToken": result.get("RefreshToken"),
            "expiresIn": result.get("ExpiresIn"),
            "tokenType": result.get("TokenType", "Bearer"),
            "userId": user["sub"],
            "tenantId": "",
            "displayName": user.get("name") or "運営者",
            "email": user.get("email") or email_n,
            "role": "operator",
            "storeName": "",
        }

    if not membership:
        return {"status": "forbidden", "reason": "no_membership"}

    tenant_id = str(membership.get("tenantId") or DEFAULT_TENANT_ID)
    profile = store.get_profile(tenant_id) or {}
    display = (
        str(membership.get("displayName") or "")
        or user.get("name")
        or email_n.split("@")[0]
    )
    return {
        "status": "ok",
        "accessToken": access,
        "idToken": result.get("IdToken"),
        "refreshToken": result.get("RefreshToken"),
        "expiresIn": result.get("ExpiresIn"),
        "tokenType": result.get("TokenType", "Bearer"),
        "userId": user["sub"],
        "tenantId": tenant_id,
        "displayName": display,
        "email": user.get("email") or email_n,
        "role": str(membership.get("role") or "tenant_admin"),
        "storeName": profile.get("name", ""),
    }


def logout_access_token(access_token: str) -> dict[str, Any]:
    if not access_token:
        return {"status": "ok"}
    try:
        _cognito().global_sign_out(AccessToken=access_token)
    except ClientError:
        pass
    return {"status": "ok"}


def session_from_access_token(
    store: BookingStore, access_token: str
) -> dict[str, Any] | None:
    try:
        user = get_user_from_access_token(access_token)
    except ClientError:
        return None

    username = user.get("username") or user.get("email") or ""
    if user_in_operator_group(username):
        return {
            "userId": user["sub"],
            "tenantId": "",
            "displayName": user.get("name") or "運営者",
            "email": user.get("email") or "",
            "role": "operator",
            "storeName": "",
        }

    membership = active_membership(store, user["sub"])
    if not membership:
        return None
    tenant_id = str(membership.get("tenantId") or "")
    profile = store.get_profile(tenant_id) or {}
    return {
        "userId": user["sub"],
        "tenantId": tenant_id,
        "displayName": str(
            membership.get("displayName") or user.get("name") or user.get("email") or ""
        ),
        "email": user.get("email") or "",
        "role": str(membership.get("role") or "tenant_admin"),
        "storeName": profile.get("name", ""),
    }


def session_payload(session: dict) -> dict[str, Any]:
    return {
        "status": "ok",
        "userId": session.get("userId"),
        "tenantId": session.get("tenantId"),
        "displayName": session.get("displayName"),
        "email": session.get("email"),
        "role": session.get("role"),
        "storeName": session.get("storeName"),
    }


def bearer_token(event: dict[str, Any] | None) -> str | None:
    if not event:
        return None
    headers = event.get("headers") or {}
    raw = headers.get("authorization") or headers.get("Authorization") or ""
    if isinstance(raw, str) and raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return None


def require_session(store: BookingStore, event: dict[str, Any] | None) -> dict[str, Any]:
    token = bearer_token(event)
    if not token:
        return {
            "ok": False,
            "status_code": 401,
            "body": {"status": "unauthorized", "reason": "missing_token"},
        }
    session = session_from_access_token(store, token)
    if not session:
        return {
            "ok": False,
            "status_code": 401,
            "body": {"status": "unauthorized", "reason": "invalid_or_expired_session"},
        }
    return {"ok": True, "session": session, "token": token}


def require_operator(store: BookingStore, event: dict[str, Any] | None) -> dict[str, Any]:
    auth = require_session(store, event)
    if not auth["ok"]:
        return auth
    if auth["session"].get("role") != "operator":
        return {
            "ok": False,
            "status_code": 403,
            "body": {"status": "forbidden", "reason": "operator_only"},
        }
    return auth


def provision_store_user(*, email: str, name: str, temporary_password: str) -> dict[str, Any]:
    """Create Cognito user for an approved store contact. Returns sub + password."""
    cfg = cognito_config()
    pool_id = cfg.get("userPoolId") or ""
    if not pool_id:
        return {"status": "error", "reason": "cognito_not_configured"}

    email_n = email.strip().lower()
    cognito = _cognito()
    try:
        cognito.admin_create_user(
            UserPoolId=pool_id,
            Username=email_n,
            UserAttributes=[
                {"Name": "email", "Value": email_n},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "name", "Value": name or email_n},
            ],
            MessageAction="SUPPRESS",
            TemporaryPassword=temporary_password,
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "UsernameExistsException":
            return {"status": "error", "reason": exc.response["Error"]["Code"]}

    cognito.admin_set_user_password(
        UserPoolId=pool_id,
        Username=email_n,
        Password=temporary_password,
        Permanent=True,
    )
    user = cognito.admin_get_user(UserPoolId=pool_id, Username=email_n)
    attrs = {a["Name"]: a["Value"] for a in user.get("UserAttributes", [])}
    sub = attrs.get("sub")
    if not sub:
        return {"status": "error", "reason": "missing_sub"}
    return {
        "status": "ok",
        "userId": sub,
        "temporaryPassword": temporary_password,
        "email": email_n,
    }

"""Auth helpers focused on membership resolution (Cognito calls mocked)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from booking import auth as auth_mod


class FakeStore:
    def __init__(self):
        self.items: dict[tuple[str, str], dict] = {}
        self.profile = {
            "name": "デモ食堂さくら",
            "status": "active",
            "tenantId": "t_demo_001",
        }

    def put_item(self, item: dict) -> None:
        self.items[(item["PK"], item["SK"])] = item

    @property
    def table(self):
        return self

    def get_item(self, Key):
        item = self.items.get((Key["PK"], Key["SK"]))
        return {"Item": item} if item else {}

    def query(self, **kwargs):
        items = [
            v
            for (p, s), v in self.items.items()
            if p.startswith("USER#") and s.startswith("MEMBERSHIP#")
        ]
        return {"Items": items}

    def get_profile(self, tenant_id: str):
        return self.profile if tenant_id == "t_demo_001" else None


def test_session_from_access_token():
    store = FakeStore()
    store.put_item(
        {
            "PK": "USER#sub-123",
            "SK": "MEMBERSHIP#t_demo_001",
            "tenantId": "t_demo_001",
            "role": "tenant_admin",
            "status": "active",
            "displayName": "さくら店長",
        }
    )

    with (
        patch.object(
            auth_mod,
            "get_user_from_access_token",
            return_value={
                "sub": "sub-123",
                "email": "demo@sakura.local",
                "name": "さくら店長",
                "username": "demo@sakura.local",
            },
        ),
        patch.object(auth_mod, "user_in_operator_group", return_value=False),
    ):
        session = auth_mod.session_from_access_token(store, "fake-token")
    assert session is not None
    assert session["tenantId"] == "t_demo_001"
    assert session["displayName"] == "さくら店長"


def test_login_with_password_success():
    store = FakeStore()
    store.put_item(
        {
            "PK": "USER#sub-123",
            "SK": "MEMBERSHIP#t_demo_001",
            "tenantId": "t_demo_001",
            "role": "tenant_admin",
            "status": "active",
            "displayName": "さくら店長",
        }
    )

    with (
        patch.object(
            auth_mod,
            "cognito_config",
            return_value={"clientId": "abc", "userPoolId": "pool", "region": "test-region"},
        ),
        patch.object(auth_mod, "_cognito") as cognito_factory,
        patch.object(auth_mod, "BookingStore", return_value=store),
        patch.object(
            auth_mod,
            "get_user_from_access_token",
            return_value={
                "sub": "sub-123",
                "email": "demo@sakura.local",
                "name": "さくら店長",
                "username": "demo@sakura.local",
            },
        ),
        patch.object(auth_mod, "user_in_operator_group", return_value=False),
    ):
        client = cognito_factory.return_value
        client.initiate_auth.return_value = {
            "AuthenticationResult": {
                "AccessToken": "access",
                "IdToken": "id",
                "RefreshToken": "refresh",
                "ExpiresIn": 3600,
            }
        }
        result = auth_mod.login_with_password(
            email="demo@sakura.local", password="Demo-pass-2026!"
        )

    assert result["status"] == "ok"
    assert result["accessToken"] == "access"
    assert result["tenantId"] == "t_demo_001"


def test_login_operator_without_membership():
    store = FakeStore()
    with (
        patch.object(
            auth_mod,
            "cognito_config",
            return_value={"clientId": "abc", "userPoolId": "pool", "region": "test-region"},
        ),
        patch.object(auth_mod, "_cognito") as cognito_factory,
        patch.object(auth_mod, "BookingStore", return_value=store),
        patch.object(
            auth_mod,
            "get_user_from_access_token",
            return_value={
                "sub": "op-1",
                "email": "operator@sakura.local",
                "name": "運営者",
                "username": "operator@sakura.local",
            },
        ),
        patch.object(auth_mod, "user_in_operator_group", return_value=True),
    ):
        client = cognito_factory.return_value
        client.initiate_auth.return_value = {
            "AuthenticationResult": {
                "AccessToken": "access-op",
                "ExpiresIn": 3600,
            }
        }
        result = auth_mod.login_with_password(
            email="operator@sakura.local", password="Demo-pass-2026!"
        )

    assert result["status"] == "ok"
    assert result["role"] == "operator"
    assert result["accessToken"] == "access-op"

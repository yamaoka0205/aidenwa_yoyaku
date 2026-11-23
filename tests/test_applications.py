"""Store application create / list / review."""

from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from booking import applications as apps


class FakeTable:
    def __init__(self):
        self.items: dict[tuple[str, str], dict] = {}

    def put_item(self, Item=None, **kwargs):
        item = Item or kwargs.get("Item")
        self.items[(item["PK"], item["SK"])] = dict(item)

    def get_item(self, Key):
        item = self.items.get((Key["PK"], Key["SK"]))
        return {"Item": item} if item else {}

    def query(self, **kwargs):
        # Simple filter for APP / APPLICATION#
        items = [
            v
            for (p, s), v in self.items.items()
            if p == "APP" and s.startswith("APPLICATION#")
        ]
        return {"Items": items}


class FakeStore:
    def __init__(self):
        self.table = FakeTable()

    def put_item(self, item: dict) -> None:
        self.table.put_item(Item=item)


def test_create_and_list_application():
    store = FakeStore()
    created = apps.create_application(
        store,
        store_name="テスト食堂",
        contact_name="山田",
        contact_email="yama@example.com",
        contact_phone="0311112222",
        note="席8卓",
    )
    assert created["status"] == "ok"
    listed = apps.list_applications(store, status="pending")
    assert listed["count"] == 1
    assert listed["applications"][0]["storeName"] == "テスト食堂"


def test_review_approve_seeds_tenant():
    store = FakeStore()
    created = apps.create_application(
        store,
        store_name="承認食堂",
        contact_name="佐藤",
        contact_email="sato@example.com",
    )
    app_id = created["applicationId"]
    result = apps.review_application(
        store,
        application_id=app_id,
        decision="approve",
        reviewer_user_id="op-1",
        provision_user={"userId": "user-new", "temporaryPassword": "Tmp-Abc12345!"},
    )
    assert result["status"] == "ok"
    assert result["tenantId"].startswith("t_")
    assert result["temporaryPassword"] == "Tmp-Abc12345!"
    # profile + membership written
    keys = set(store.table.items.keys())
    assert any(k[1] == "PROFILE" for k in keys)
    assert ("USER#user-new", f"MEMBERSHIP#{result['tenantId']}") in keys


def test_review_reject():
    store = FakeStore()
    created = apps.create_application(
        store,
        store_name="却下食堂",
        contact_name="鈴木",
        contact_email="suzu@example.com",
    )
    result = apps.review_application(
        store,
        application_id=created["applicationId"],
        decision="reject",
        reviewer_user_id="op-1",
        reject_reason="情報不足",
    )
    assert result["status"] == "ok"
    assert result["application"]["status"] == "rejected"
    assert result["application"]["rejectReason"] == "情報不足"

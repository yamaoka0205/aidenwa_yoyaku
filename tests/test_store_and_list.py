"""Unit tests for store view and reservation listing (no AWS)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from booking.reservations import list_reservations
from booking.store_view import get_store, update_store


class FakeStore:
    def __init__(self):
        self.profile = {
            "PK": "TENANT#t_demo_001",
            "SK": "PROFILE",
            "tenantId": "t_demo_001",
            "name": "デモ食堂さくら",
            "status": "active",
            "timezone": "Asia/Tokyo",
            "standardDurationMin": 120,
            "reservationSlotMin": 15,
            "inboundId": "+810000000001",
        }
        self.hours = [
            {
                "PK": "TENANT#t_demo_001",
                "SK": "HOURS#mon",
                "openTime": "11:00",
                "closeTime": "22:00",
                "lastStartTime": "20:00",
                "isClosed": False,
            }
        ]
        self.tables = [
            {
                "tableId": "T4-01",
                "label": "4人用A",
                "capacity": 4,
                "aiBookable": True,
                "active": True,
                "sortOrder": 1,
            }
        ]
        self.faqs = [
            {
                "SK": "FAQ#f001",
                "question": "駐車場は？",
                "answer": "近隣あり",
                "tags": ["駐車"],
                "enabled": True,
                "sortOrder": 1,
            }
        ]
        self.reservations = [
            {
                "reservationId": "r2",
                "date": "2026-11-20",
                "startTime": "19:00",
                "endTime": "21:00",
                "partySize": 4,
                "customerName": "ヤマダ",
                "status": "confirmed",
                "source": "ai_phone",
                "tableId": "T4-01",
            },
            {
                "reservationId": "r1",
                "date": "2026-11-20",
                "startTime": "18:00",
                "endTime": "20:00",
                "partySize": 2,
                "customerName": "スズキ",
                "status": "confirmed",
                "source": "manual",
                "tableId": "T4-02",
            },
            {
                "reservationId": "r0",
                "date": "2026-11-20",
                "startTime": "12:00",
                "endTime": "14:00",
                "partySize": 2,
                "customerName": "キャンセル",
                "status": "cancelled",
                "source": "manual",
            },
        ]
        self.puts: list[dict] = []

    def get_profile(self, tenant_id: str):
        return self.profile if tenant_id == "t_demo_001" else None

    def list_hours(self, tenant_id: str):
        return list(self.hours)

    def list_tables(self, tenant_id: str):
        return list(self.tables)

    def list_reservations_for_date(self, tenant_id: str, date_s: str):
        return [r for r in self.reservations if r["date"] == date_s]

    def put_item(self, item: dict) -> None:
        self.puts.append(item)
        if item.get("SK") == "PROFILE":
            self.profile = item
        elif str(item.get("SK", "")).startswith("HOURS#"):
            self.hours = [h for h in self.hours if h["SK"] != item["SK"]] + [item]
        elif str(item.get("SK", "")).startswith("FAQ#"):
            self.faqs = [f for f in self.faqs if f["SK"] != item["SK"]] + [item]


def test_list_reservations_sorted_and_skips_cancelled():
    store = FakeStore()
    result = list_reservations(store, tenant_id="t_demo_001", date_s="2026-11-20")
    assert result["status"] == "ok"
    assert result["count"] == 2
    assert result["partyTotal"] == 6
    assert [r["startTime"] for r in result["reservations"]] == ["18:00", "19:00"]


def test_get_and_update_store(monkeypatch):
    import booking.store_view as store_view

    store = FakeStore()
    monkeypatch.setattr(store_view, "list_faqs", lambda s, t: store.faqs)
    got = get_store(store, "t_demo_001")
    assert got["status"] == "ok"
    assert got["name"] == "デモ食堂さくら"
    assert got["tables"][0]["tableId"] == "T4-01"

    updated = update_store(
        store,
        tenant_id="t_demo_001",
        name="さくら食堂",
        standard_duration_min=90,
        hours=[
            {
                "dow": "mon",
                "openTime": "12:00",
                "closeTime": "21:00",
                "isClosed": False,
            }
        ],
        faqs=[{"faqId": "f001", "question": "禁煙？", "answer": "店内禁煙です", "enabled": True}],
    )
    assert updated["name"] == "さくら食堂"
    assert updated["standardDurationMin"] == 90
    assert any(p.get("SK") == "HOURS#mon" and p.get("openTime") == "12:00" for p in store.puts)

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from handlers.resolve_store import _menu_prompt, handler  # noqa: E402


def test_menu_prompt_includes_store_name():
    text = _menu_prompt("デモ食堂さくら")
    assert "デモ食堂さくらです" in text
    assert text.startswith("お電話ありがとうございます。")
    assert "ご予約を承ります" in text


def test_resolve_store_webrtc_returns_menu_prompt(monkeypatch):
    store = MagicMock()
    store.get_inbound.return_value = {"tenantId": "t_demo_001"}
    store.get_profile.return_value = {
        "tenantId": "t_demo_001",
        "name": "デモ食堂さくら",
        "status": "active",
        "transferPhoneNumber": "",
    }
    monkeypatch.setattr("handlers.resolve_store.BookingStore", lambda: store)

    event = {
        "Details": {
            "ContactData": {
                "InitiationMethod": "WEBRTC_API",
                "SegmentAttributes": {
                    "connect:Subtype": {"ValueString": "connect:WebRTC"}
                },
                "SystemEndpoint": {},
                "CustomerEndpoint": {},
            }
        }
    }
    result = handler(event)
    assert result["found"] == "true"
    assert result["storeName"] == "デモ食堂さくら"
    assert "デモ食堂さくらです" in result["menuPrompt"]
    assert "ご予約を承ります" in result["menuPrompt"]

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from booking.extract import extract_with_rules  # noqa: E402
from booking.dialog import handle_reservation_turn, PROMPTS  # noqa: E402
from booking.faq import match_faq  # noqa: E402
from booking.availability import AvailabilityResult  # noqa: E402
from booking.confirm import ConfirmResult  # noqa: E402


def test_extract_tomorrow_evening_party():
    slots = extract_with_rules("明日の19時半に4人でお願いします")
    assert slots.time == "19:30"
    assert slots.party_size == 4
    assert slots.date is not None


def test_extract_bare_party_digit_from_asr():
    assert extract_with_rules("4").party_size == 4
    assert extract_with_rules("４").party_size == 4
    assert extract_with_rules("よにん").party_size == 4


def test_extract_weekday():
    slots = extract_with_rules("来週の金曜日の18時に2名")
    assert slots.time == "18:00"
    assert slots.party_size == 2
    assert slots.date is not None


def test_dialog_asks_one_field_at_a_time(monkeypatch):
    store = MagicMock()

    def fake_avail(*args, **kwargs):
        return AvailabilityResult(
            status="available",
            tenantId="t_demo_001",
            date=kwargs["date_s"],
            startTime=kwargs["start_time_s"],
            endTime="21:00",
            partySize=kwargs["party_size"],
            tableId="T4-01",
            capacity=4,
            candidateTableIds=["T4-01"],
            standardDurationMin=120,
        )

    monkeypatch.setattr("booking.dialog.check_availability", fake_avail)

    r0 = handle_reservation_turn(store, tenant_id="t_demo_001", utterance="")
    assert r0["step"] == "party_size"
    assert "人数" in r0["prompt"]

    r1 = handle_reservation_turn(
        store, tenant_id="t_demo_001", utterance="4人", state_data=r0
    )
    assert r1["partySize"] == "4"
    assert r1["step"] == "date"

    r2 = handle_reservation_turn(
        store, tenant_id="t_demo_001", utterance="明日", state_data=r1
    )
    assert r2["date"]
    assert r2["step"] == "time"

    r3 = handle_reservation_turn(
        store, tenant_id="t_demo_001", utterance="19時半", state_data=r2
    )
    assert r3["time"] == "19:30"
    assert r3["step"] == "name"

    r4 = handle_reservation_turn(
        store, tenant_id="t_demo_001", utterance="ヤマダです", state_data=r3
    )
    assert r4["name"] == "ヤマダ"
    assert r4["phase"] == "confirm"
    assert "4名のヤマダ様" in r4["prompt"]

    def fake_confirm(*args, **kwargs):
        return ConfirmResult(
            status="confirmed",
            tenantId="t_demo_001",
            reservationId="rid1",
            date=kwargs["date_s"],
            startTime=kwargs["start_time_s"],
            endTime="21:00",
            partySize=kwargs["party_size"],
            tableId="T4-01",
            capacity=4,
            customerName=kwargs["customer_name"],
            source="ai_phone",
            standardDurationMin=120,
        )

    monkeypatch.setattr("booking.dialog.confirm_reservation", fake_confirm)
    r5 = handle_reservation_turn(
        store,
        tenant_id="t_demo_001",
        utterance="",
        state_data=r4,
        dtmf="1",
    )
    assert r5["phase"] == "done"
    assert r5["resultStatus"] == "confirmed"
    assert "承りました" in r5["prompt"]


def test_confirm_accepts_utterance_digit_without_dtmf(monkeypatch):
    """Lex delivers keypad 1 as inputTranscript; must not re-loop confirm."""
    store = MagicMock()

    def fake_avail(*args, **kwargs):
        return AvailabilityResult(
            status="available",
            tenantId="t_demo_001",
            date=kwargs["date_s"],
            startTime=kwargs["start_time_s"],
            endTime="21:00",
            partySize=kwargs["party_size"],
            tableId="T4-01",
            capacity=4,
            candidateTableIds=["T4-01"],
            standardDurationMin=120,
        )

    def fake_confirm(*args, **kwargs):
        return ConfirmResult(
            status="confirmed",
            tenantId="t_demo_001",
            reservationId="rid1",
            date=kwargs["date_s"],
            startTime=kwargs["start_time_s"],
            endTime="21:00",
            partySize=kwargs["party_size"],
            tableId="T4-01",
            capacity=4,
            customerName=kwargs["customer_name"],
            source="ai_phone",
            standardDurationMin=120,
        )

    monkeypatch.setattr("booking.dialog.check_availability", fake_avail)
    monkeypatch.setattr("booking.dialog.confirm_reservation", fake_confirm)

    state = {
        "step": "confirm",
        "phase": "confirm",
        "date": "2026-12-01",
        "time": "19:00",
        "partySize": "4",
        "name": "ヤマダ",
    }
    r = handle_reservation_turn(
        store, tenant_id="t_demo_001", utterance="1", state_data=state, dtmf=None
    )
    assert r["phase"] == "done"
    assert r["resultStatus"] == "confirmed"

    r2 = handle_reservation_turn(
        store, tenant_id="t_demo_001", utterance="２", state_data=state, dtmf=None
    )
    assert r2["step"] == "party_size"
    assert r2["phase"] == "collect"


def test_party_size_dtmf_and_handoff():
    store = MagicMock()
    r0 = handle_reservation_turn(store, tenant_id="t_demo_001", utterance="")
    r1 = handle_reservation_turn(
        store, tenant_id="t_demo_001", utterance="", state_data=r0, dtmf="4"
    )
    assert r1["partySize"] == "4"
    assert r1["step"] == "date"

    r7 = handle_reservation_turn(
        store, tenant_id="t_demo_001", utterance="", state_data=r0, dtmf="7"
    )
    assert r7["action"] == "handoff"


def test_faq_match():
    faqs = [
        {
            "SK": "FAQ#hours",
            "question": "営業時間は何時から何時までですか",
            "answer": "11時から22時です",
            "tags": ["営業", "時間"],
        }
    ]
    m = match_faq(faqs, "営業時間を教えて")
    assert m is not None
    assert m["SK"] == "FAQ#hours"

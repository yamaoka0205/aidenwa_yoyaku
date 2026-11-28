"""Reservation dialog: ask party → date → time → family name, then confirm."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from booking.availability import check_availability
from booking.confirm import confirm_reservation
from booking.db import BookingStore
from booking.extract import extract_with_rules, extract_slots
from booking.timeutil import parse_date

WEEKDAY_JA = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]

# Ask one field at a time (ASR is more reliable on short answers).
STEPS = ("party_size", "date", "time", "name")

PROMPTS = {
    "party_size": "人数は何人ですか。1から6の数字でお答えください。ボタンでも入力できます。",
    "date": "ご希望の日はいつですか。",
    "time": "何時からご利用ですか。15分刻みでお願いします。",
    "name": "お名前を、名字だけカタカナでお願いします。",
}


@dataclass
class DialogState:
    tenant_id: str
    date: str | None = None
    time: str | None = None
    party_size: int | None = None
    name: str | None = None
    step: str = "party_size"  # party_size | date | time | name | confirm | done
    phase: str = "collect"  # collect | confirm | done (kept for Connect/Lex attrs)
    last_prompt: str = ""
    result_status: str = ""
    reservation_id: str = ""


def _normalize_family_name(text: str) -> str | None:
    """Keep family name only, prefer katakana."""
    t = (text or "").strip()
    t = re.sub(r"(です|でお願いします|と申します|といいます)$", "", t).strip()
    t = re.sub(r"^(名字|氏名|名前)[はが]?", "", t).strip()
    # "ヤマダタロウ" → first katakana run as family name guess if long; prefer explicit space
    if " " in t or "　" in t:
        t = re.split(r"[ 　]+", t)[0]
    m = re.search(r"[ァ-ヶー]{2,10}", t)
    if m:
        return m.group(0)
    # fallback: short non-empty token without digits
    m = re.search(r"[一-龥ぁ-んァ-ヶー]{1,10}", t)
    if m and not re.search(r"\d", m.group(0)):
        # If hiragana/kanji, still store as-is; Lex often returns katakana
        return m.group(0)
    return None


def _party_from_dtmf(dtmf: str | None) -> int | None:
    if not dtmf or not str(dtmf).isdigit():
        return None
    n = int(str(dtmf))
    if 1 <= n <= 6:
        return n
    return None


def _apply_current_step(state: DialogState, utterance: str, dtmf: str | None) -> bool:
    """Fill only the field for state.step. Returns True if that field was set."""
    text = utterance or ""
    if state.step == "party_size":
        if dtmf and str(dtmf).isdigit():
            n = int(str(dtmf))
            if n >= 7 or 1 <= n <= 6:
                state.party_size = n
                return True
            return False
        slots = extract_with_rules(text)
        n = slots.party_size
        if n is not None:
            state.party_size = n
            return True
        return False

    if state.step == "date":
        # Rules first (明日/来週の金曜); Bedrock fills harder relative phrasing.
        slots = extract_with_rules(text)
        if slots.date:
            state.date = slots.date
            return True
        slots_b = extract_slots(text)
        if slots_b.date:
            state.date = slots_b.date
            return True
        return False

    if state.step == "time":
        slots = extract_with_rules(text)
        if slots.time:
            state.time = slots.time
            return True
        # Bedrock only if rules miss (e.g. 「夜の七時半」)
        slots_b = extract_slots(text)
        if slots_b.time:
            state.time = slots_b.time
            return True
        return False

    if state.step == "name":
        name = _normalize_family_name(text)
        if not name:
            slots = extract_with_rules(text)
            if slots.name:
                name = _normalize_family_name(slots.name)
        if name:
            state.name = name
            return True
        return False

    return False


def _next_step(state: DialogState) -> str:
    if state.party_size is None:
        return "party_size"
    if state.party_size >= 7:
        return "handoff"
    if not state.date:
        return "date"
    if not state.time:
        return "time"
    if not state.name:
        return "name"
    return "confirm"


def _confirm_text(state: DialogState) -> str:
    d = parse_date(state.date)  # type: ignore[arg-type]
    weekday = WEEKDAY_JA[d.weekday()]
    return (
        f"{state.party_size}名の{state.name}様、"
        f"{d.month}月{d.day}日 {weekday} {state.time}でよろしいですか。"
        "よろしければ1を、訂正する場合は2を押してください。"
    )


def _reset_for_correction(state: DialogState) -> None:
    state.date = None
    state.time = None
    state.party_size = None
    state.name = None
    state.step = "party_size"
    state.phase = "collect"
    state.last_prompt = "もう一度伺います。" + PROMPTS["party_size"]


_DIGIT_TRANS = str.maketrans("１２", "12")


def _confirm_choice(dtmf: str | None, utterance: str | None) -> str | None:
    """Lex often delivers keypad 1/2 as inputTranscript, not a separate dtmf field."""
    for raw in (dtmf, utterance):
        if raw is None:
            continue
        token = str(raw).strip().translate(_DIGIT_TRANS)
        if token in ("1", "2"):
            return token
    return None


def state_from_dict(data: dict[str, Any]) -> DialogState:
    phase = str(data.get("phase") or "collect")
    date = data.get("date") or None
    time = data.get("time") or data.get("startTime") or None
    party_size = (
        int(data["partySize"]) if data.get("partySize") not in (None, "") else None
    )
    name = data.get("name") or data.get("customerName") or None
    step = str(data.get("step") or "")
    if not step:
        if phase == "confirm":
            step = "confirm"
        elif phase == "done":
            step = "done"
        elif party_size is None:
            step = "party_size"
        elif not date:
            step = "date"
        elif not time:
            step = "time"
        elif not name:
            step = "name"
        else:
            step = "confirm"
    return DialogState(
        tenant_id=str(data.get("tenantId") or data.get("tenant_id") or ""),
        date=date,
        time=time,
        party_size=party_size,
        name=name,
        step=step,
        phase=phase,
        last_prompt=str(data.get("lastPrompt") or ""),
        result_status=str(data.get("resultStatus") or ""),
        reservation_id=str(data.get("reservationId") or ""),
    )


def state_to_dict(state: DialogState) -> dict[str, Any]:
    d = asdict(state)
    return {
        "tenantId": d["tenant_id"],
        "date": d["date"] or "",
        "time": d["time"] or "",
        "partySize": "" if d["party_size"] is None else str(d["party_size"]),
        "name": d["name"] or "",
        "step": d["step"],
        "phase": d["phase"],
        "lastPrompt": d["last_prompt"],
        "resultStatus": d["result_status"],
        "reservationId": d["reservation_id"],
        "missing": "",
    }


def handle_reservation_turn(
    store: BookingStore,
    *,
    tenant_id: str,
    utterance: str,
    state_data: dict[str, Any] | None = None,
    dtmf: str | None = None,
    caller_number: str | None = None,
    caller_number_available: bool = False,
) -> dict[str, Any]:
    state = state_from_dict({"tenantId": tenant_id, **(state_data or {})})
    state.tenant_id = tenant_id

    # First turn with empty state → open with party-size question
    if (
        state.step == "party_size"
        and state.party_size is None
        and not (utterance or "").strip()
        and not dtmf
    ):
        state.phase = "collect"
        state.last_prompt = PROMPTS["party_size"]
        out = state_to_dict(state)
        out["prompt"] = state.last_prompt
        out["action"] = "listen"
        return out

    if state.step == "confirm":
        choice = _confirm_choice(dtmf, utterance)
        if choice == "1":
            result = confirm_reservation(
                store,
                tenant_id=tenant_id,
                date_s=str(state.date),
                start_time_s=str(state.time),
                party_size=int(state.party_size),  # type: ignore[arg-type]
                customer_name=str(state.name),
                customer_phone=caller_number if caller_number_available else None,
                source="ai_phone",
            )
            if result.status == "confirmed":
                state.step = "done"
                state.phase = "done"
                state.result_status = "confirmed"
                state.reservation_id = result.reservationId or ""
                state.last_prompt = "ご予約を承りました。当日お待ちしております。"
            elif result.status == "full":
                state.time = None
                state.step = "time"
                state.phase = "collect"
                state.last_prompt = (
                    "申し訳ありません、その時間は満席です。" + PROMPTS["time"]
                )
            else:
                _reset_for_correction(state)
                state.last_prompt = (
                    f"予約を確定できませんでした。{result.reason or result.status}。"
                    + PROMPTS["party_size"]
                )
            out = state_to_dict(state)
            out["prompt"] = state.last_prompt
            out["action"] = "speak" if state.phase == "done" else "listen"
            return out
        if choice == "2":
            _reset_for_correction(state)
            out = state_to_dict(state)
            out["prompt"] = state.last_prompt
            out["action"] = "listen"
            return out
        # Unrecognized input on confirm → re-ask (do not re-run availability).
        state.phase = "confirm"
        state.last_prompt = _confirm_text(state)
        out = state_to_dict(state)
        out["prompt"] = state.last_prompt
        out["action"] = "confirm_dtmf"
        return out

    # Collect current field only
    if state.step in STEPS:
        ok = _apply_current_step(state, utterance, dtmf)
        if not ok:
            state.phase = "collect"
            state.last_prompt = "うまく聞き取れませんでした。" + PROMPTS[state.step]
            out = state_to_dict(state)
            out["prompt"] = state.last_prompt
            out["action"] = "listen"
            return out

    nxt = _next_step(state)
    if nxt == "handoff":
        state.step = "done"
        state.phase = "done"
        state.result_status = "human_handoff"
        state.last_prompt = "人数が多いため、担当者におつなぎします。"
        out = state_to_dict(state)
        out["prompt"] = state.last_prompt
        out["action"] = "handoff"
        return out

    if nxt in STEPS:
        state.step = nxt
        state.phase = "collect"
        state.last_prompt = PROMPTS[nxt]
        out = state_to_dict(state)
        out["prompt"] = state.last_prompt
        out["action"] = "listen"
        return out

    # All fields present → availability then confirm
    avail = check_availability(
        store,
        tenant_id=tenant_id,
        date_s=str(state.date),
        start_time_s=str(state.time),
        party_size=int(state.party_size),  # type: ignore[arg-type]
    )
    if avail.status == "human_handoff":
        state.step = "done"
        state.phase = "done"
        state.result_status = "human_handoff"
        state.last_prompt = "人数が多いため、担当者におつなぎします。"
        out = state_to_dict(state)
        out["prompt"] = state.last_prompt
        out["action"] = "handoff"
        return out
    if avail.status != "available":
        reasons = {
            "full": ("time", "その時間は満席です。" + PROMPTS["time"]),
            "closed": ("date", "その日は定休日です。" + PROMPTS["date"]),
            "outside_hours": ("time", "その時刻は営業時間外です。" + PROMPTS["time"]),
            "invalid_slot": ("time", "開始時刻は15分刻みでお願いします。" + PROMPTS["time"]),
        }
        step, prompt = reasons.get(
            avail.status, ("date", "予約できない日時です。" + PROMPTS["date"])
        )
        if step == "time":
            state.time = None
        if step == "date":
            state.date = None
            state.time = None
        state.step = step
        state.phase = "collect"
        state.last_prompt = prompt
        out = state_to_dict(state)
        out["prompt"] = state.last_prompt
        out["action"] = "listen"
        return out

    state.step = "confirm"
    state.phase = "confirm"
    state.last_prompt = _confirm_text(state)
    out = state_to_dict(state)
    out["prompt"] = state.last_prompt
    out["action"] = "confirm_dtmf"
    return out

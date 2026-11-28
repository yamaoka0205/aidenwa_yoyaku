"""Connect/Lex turn handler for reservation dialog.

Accepts either:
  - Connect Lambda event (Details.Parameters + ContactData.Attributes)
  - Lex V2 code-hook event
  - Direct JSON for local tests
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from booking.db import BookingStore
from booking.dialog import handle_reservation_turn, state_from_dict


def _slot_interpreted(event: dict[str, Any], slot_name: str) -> str | None:
    intent = ((event.get("sessionState") or {}).get("intent") or {})
    slot = (intent.get("slots") or {}).get(slot_name) or {}
    value = slot.get("value") or {}
    raw = value.get("interpretedValue") or value.get("originalValue")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _attrs(event: dict[str, Any]) -> dict[str, Any]:
    details = event.get("Details") or {}
    contact = details.get("ContactData") or {}
    params = details.get("Parameters") or {}
    attrs = dict(contact.get("Attributes") or {})
    attrs.update(params)
    if event.get("sessionState"):
        # Lex V2
        sess = event["sessionState"].get("sessionAttributes") or {}
        attrs.update(sess)
        input_transcript = event.get("inputTranscript") or ""
        if input_transcript:
            attrs.setdefault("utterance", input_transcript)
        # Keypad on Confirmation slot arrives as slot value, not session dtmf.
        conf = _slot_interpreted(event, "Confirmation")
        if conf and not attrs.get("dtmf"):
            attrs["dtmf"] = conf
    if "body" in event and isinstance(event["body"], str):
        try:
            attrs.update(json.loads(event["body"] or "{}"))
        except json.JSONDecodeError:
            pass
    for k in (
        "tenantId",
        "utterance",
        "dtmf",
        "phase",
        "step",
        "date",
        "time",
        "partySize",
        "name",
    ):
        if k in event and k not in attrs:
            attrs[k] = event[k]
    return attrs


def _lex_response(result: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Helpdesk-style: Lex closes each turn; Connect plays prompt and branches.

    Lex is ASR only for this turn. Lambda writes sessionAttributes
    (prompt / routingAction / dialog state). Connect MessageParticipant reads
    ``$.Lex.SessionAttributes.aiResponseText`` and Compare reads routingAction.
    """
    session = dict((event.get("sessionState") or {}).get("sessionAttributes") or {})
    session.update({k: ("" if v is None else str(v)) for k, v in result.items()})
    session["prompt"] = result.get("prompt") or ""
    session["aiResponseText"] = result.get("aiResponseText") or session["prompt"]
    session["routingAction"] = result.get("routingAction") or "LISTEN"
    session.setdefault("intentHint", "BookReservation")
    intent_name = (
        ((event.get("sessionState") or {}).get("intent") or {}).get("name")
        or "FallbackIntent"
    )
    # Top-level keys too (some Connect mappings read them alongside sessionState).
    return {
        **{k: session[k] for k in session},
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {"name": intent_name, "state": "Fulfilled"},
            "sessionAttributes": session,
        },
        "messages": [],
    }


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
    event = event or {}
    attrs = _attrs(event)
    tenant_id = str(attrs.get("tenantId") or "")
    utterance = str(attrs.get("utterance") or attrs.get("inputTranscript") or "")
    dtmf = attrs.get("dtmf") or attrs.get("StoredCustomerInput") or None
    if dtmf is not None:
        dtmf = str(dtmf)

    state_keys = (
        "date",
        "time",
        "partySize",
        "name",
        "step",
        "phase",
        "lastPrompt",
        "resultStatus",
        "reservationId",
        "missing",
    )
    def _kept(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        return True

    state_data = {k: attrs.get(k) for k in state_keys if _kept(attrs.get(k))}
    if isinstance(state_data.get("missing"), str):
        state_data["missing"] = [
            x for x in str(state_data["missing"]).split(",") if x
        ]

    # Connect GetParticipantInput(StoreInput=True) → $.StoredCustomerInput
    contact = ((event.get("Details") or {}).get("ContactData") or {})
    stored = contact.get("StoredCustomerInput") or attrs.get("StoredCustomerInput")
    if not dtmf and stored not in (None, ""):
        dtmf = str(stored).strip()

    caller_available = str(attrs.get("callerNumberAvailable") or "").lower() == "true"
    result = handle_reservation_turn(
        BookingStore(),
        tenant_id=tenant_id,
        utterance=utterance,
        state_data=state_data,
        dtmf=dtmf,
        caller_number=attrs.get("callerNumber"),
        caller_number_available=caller_available,
    )

    if event.get("sessionState") is not None or event.get("bot") is not None:
        return _lex_response(result, event)

    # Connect STRING_MAP / direct invoke
    flat = {k: ("" if v is None else str(v)) for k, v in result.items()}
    return flat

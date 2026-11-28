"""Lex V2 alias code-hook router for BookingAppPhone."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from handlers import faq_turn, reservation_turn


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, Any]:
    """Lex code-hook router.

    Lex is ASR/TTS only. Short answers often land on AMAZON.FallbackIntent;
    Connect's intentHint chooses BookReservation vs AskFaq — not sample utterances.
    """
    event = event or {}
    session = (event.get("sessionState") or {}).get("sessionAttributes") or {}
    intent = ((event.get("sessionState") or {}).get("intent") or {}).get("name") or ""
    hint = session.get("intentHint") or ""
    transcript = event.get("inputTranscript") or ""
    print(
        json.dumps(
            {
                "phoneTurn": True,
                "intent": intent,
                "hint": hint,
                "transcript": transcript,
                "step": session.get("step"),
                "phase": session.get("phase"),
            },
            ensure_ascii=False,
        )
    )
    if hint in {"AskFaq", "BookReservation"}:
        intent = hint
    elif intent == "AskFaq":
        pass
    else:
        # BookReservation, FallbackIntent, empty → reservation dialog
        intent = "BookReservation"
    if intent == "AskFaq":
        return faq_turn.handler(event, context)
    return reservation_turn.handler(event, context)

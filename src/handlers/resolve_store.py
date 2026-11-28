"""Lambda handler: resolve the store at the start of a Connect call.

Invoked from the shared contact flow ("AWS Lambda function" block,
response validation STRING_MAP). Returns flat string values so the flow can
store them as contact attributes and read the store name in the greeting.

Output keys:
  found                  "true" / "false"
  callType               "phone" / "phone_anonymous" / "webrtc"
  tenantId, storeName, inboundId
  menuPrompt             full greeting TTS (store name baked in). Connect must
                         play $.Attributes.menuPrompt as a whole — mid-string
                         $.Attributes.storeNameです eats 「です」into the key.
  callerNumber           real number for phone; "" for phone_anonymous;
                         demo placeholder for webrtc
  callerNumberAvailable  "true" only when callerNumber is real and may be saved
  inboundIsDemo          "true" when the demo inbound number was used
  callerNumberIsDemo     "true" when callerNumber is the demo placeholder
  transferPhoneNumber    empty when unset
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from booking.db import BookingStore
from booking.inbound import endpoints_from_contact


def _flag(value: bool) -> str:
    return "true" if value else "false"


def _menu_prompt(store_name: str) -> str:
    """Greeting only (store name baked in). DTMF choices are a separate static prompt.

    Connect must not append Japanese after ``$.Attributes.storeName`` (it eats
    「です」into the attribute key). Keep this string self-contained and play it
    with MessageParticipant before GetParticipantInput.
    """
    name = (store_name or "").strip() or "当店"
    return f"お電話ありがとうございます。{name}です。"


def handler(event: dict[str, Any] | None = None, context: Any = None) -> dict[str, str]:
    contact_data = ((event or {}).get("Details") or {}).get("ContactData") or {}
    endpoints = endpoints_from_contact(contact_data)

    result = {
        "found": "false",
        "callType": endpoints.call_type,
        "tenantId": "",
        "storeName": "",
        "menuPrompt": "",
        "inboundId": endpoints.inbound_id,
        "callerNumber": endpoints.caller_number,
        "callerNumberAvailable": _flag(endpoints.caller_number_available),
        "inboundIsDemo": _flag(endpoints.inbound_is_demo),
        "callerNumberIsDemo": _flag(endpoints.caller_is_demo),
        "transferPhoneNumber": "",
    }
    if not endpoints.inbound_id:
        return result

    store = BookingStore()
    inbound = store.get_inbound(endpoints.inbound_id)
    if not inbound:
        return result

    profile = store.get_profile(inbound["tenantId"])
    if not profile or profile.get("status") != "active":
        return result

    store_name = str(profile.get("name") or "")
    result.update(
        {
            "found": "true",
            "tenantId": profile["tenantId"],
            "storeName": store_name,
            "menuPrompt": _menu_prompt(store_name),
            "transferPhoneNumber": profile.get("transferPhoneNumber", ""),
        }
    )
    return result

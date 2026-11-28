#!/usr/bin/env python3
"""Write BookingApp-Inbound Connect flow (Helpdesk-style Lex + Connect loop).

Architecture (same feel as AIHelpdeskFlow):
  ResolveStore → 挨拶 → 最初の質問を Connect が再生
  → Lex（Text は空白＝文字起こしだけ）→ Lambda が sessionAttributes に結果を書く
  → Connect が aiResponseText を再生し routingAction で分岐
      LISTEN  → また Lex
      CONFIRM → DTMF 1/2 → ReservationTurn Lambda → また分岐
      END / HANDOFF → 終了

Console で見やすいよう、ブロックを左→右・上→下に整列する。
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "infra" / "connect" / "BookingApp-Inbound.flow.json"

LAMBDA_RESOLVE = (
    "arn:aws:lambda:${AWS_DEFAULT_REGION}:${AWS_ACCOUNT_ID}:function:BookingAppResolveStore"
)
LAMBDA_TURN = (
    "arn:aws:lambda:${AWS_DEFAULT_REGION}:${AWS_ACCOUNT_ID}:function:BookingAppReservationTurn"
)
LEX_ALIAS = (
    "arn:aws:lex:${AWS_DEFAULT_REGION}:${AWS_ACCOUNT_ID}:bot-alias/"
    "${LEX_BOT_ID}/${LEX_ALIAS_ID}"
)

# Stable IDs so republish keeps the same nodes in the editor.
ids = {
    "logging": "a1000001-0000-4000-8000-000000000001",
    "set_voice": "a1000001-0000-4000-8000-000000000002",
    "resolve": "a1000001-0000-4000-8000-000000000003",
    "set_resolve": "a1000001-0000-4000-8000-000000000004",
    "check_found": "a1000001-0000-4000-8000-000000000005",
    "unknown": "a1000001-0000-4000-8000-000000000006",
    "greet": "a1000001-0000-4000-8000-000000000010",
    "ask_party": "a1000001-0000-4000-8000-000000000011",
    "lex": "a1000001-0000-4000-8000-000000000020",
    "copy_lex": "a1000001-0000-4000-8000-000000000021",
    "branch": "a1000001-0000-4000-8000-000000000022",
    "play_listen": "a1000001-0000-4000-8000-000000000030",
    "play_confirm": "a1000001-0000-4000-8000-000000000040",
    "dtmf_confirm": "a1000001-0000-4000-8000-000000000041",
    "set_dtmf_1": "a1000001-0000-4000-8000-000000000045",
    "set_dtmf_2": "a1000001-0000-4000-8000-000000000046",
    "invoke_turn": "a1000001-0000-4000-8000-000000000042",
    "copy_turn": "a1000001-0000-4000-8000-000000000043",
    "branch_turn": "a1000001-0000-4000-8000-000000000044",
    "play_end": "a1000001-0000-4000-8000-000000000050",
    "thanks": "a1000001-0000-4000-8000-000000000051",
    "play_handoff": "a1000001-0000-4000-8000-000000000060",
    "handoff": "a1000001-0000-4000-8000-000000000061",
    "bye": "a1000001-0000-4000-8000-000000000070",
}

# Grid for Connect UI (Helpdesk uses lowercase "position").
COL = 280
ROW = 190


def pos(col: int, row: int) -> dict:
    return {"x": 80 + col * COL, "y": 40 + row * ROW}


PARTY_PROMPT = "人数は何人ですか。1から6の数字でお答えください。ボタンでも入力できます。"

# Dialog state keys copied Lex ↔ Contact Attributes (Helpdesk pattern).
STATE_KEYS = (
    "step",
    "phase",
    "date",
    "time",
    "partySize",
    "name",
    "lastPrompt",
    "resultStatus",
    "reservationId",
    "prompt",
    "aiResponseText",
    "routingAction",
    "action",
)


def _lex_session_from_attrs() -> dict[str, str]:
    out = {
        "tenantId": "$.Attributes.tenantId",
        "callerNumber": "$.Attributes.callerNumber",
        "callerNumberAvailable": "$.Attributes.callerNumberAvailable",
        "storeName": "$.Attributes.storeName",
        "intentHint": "BookReservation",
    }
    for key in STATE_KEYS:
        out[key] = f"$.Attributes.{key}"
    return out


def _copy_lex_to_attrs() -> dict[str, str]:
    out = {}
    for key in STATE_KEYS:
        out[key] = f"$.Lex.SessionAttributes.{key}"
    return out


def _copy_external_to_attrs() -> dict[str, str]:
    out = {}
    for key in STATE_KEYS:
        out[key] = f"$.External.{key}"
    return out


def _meta() -> dict:
    # Explicit layout: row0 setup → row2 greet/lex → row3 branch →
    # row4 listen loop / row5 confirm / row6 end / row7 handoff
    layout = {
        ids["logging"]: pos(0, 0),
        ids["set_voice"]: pos(1, 0),
        ids["resolve"]: pos(2, 0),
        ids["set_resolve"]: pos(3, 0),
        ids["check_found"]: pos(4, 0),
        ids["unknown"]: pos(4, 1),
        ids["greet"]: pos(0, 2),
        ids["ask_party"]: pos(1, 2),
        ids["lex"]: pos(2, 2),
        ids["copy_lex"]: pos(3, 2),
        ids["branch"]: pos(4, 2),
        ids["play_listen"]: pos(2, 3),
        ids["play_confirm"]: pos(0, 4),
        ids["dtmf_confirm"]: pos(1, 4),
        ids["set_dtmf_1"]: pos(2, 4),
        ids["set_dtmf_2"]: pos(2, 5),
        ids["invoke_turn"]: pos(3, 4),
        ids["copy_turn"]: pos(4, 4),
        ids["branch_turn"]: pos(5, 4),
        ids["play_end"]: pos(0, 5),
        ids["thanks"]: pos(1, 5),
        ids["play_handoff"]: pos(0, 6),
        ids["handoff"]: pos(1, 6),
        ids["bye"]: pos(3, 5),
    }
    return {
        "EntryPointPosition": {"x": 40, "y": 40},
        "ActionMetadata": {
            i: {"position": layout[i]} for i in ids.values() if i in layout
        },
    }


def _branch_transitions(*, listen: str, confirm: str, end: str, handoff: str) -> dict:
    return {
        "NextAction": listen,
        "Conditions": [
            {
                "NextAction": confirm,
                "Condition": {"Operator": "Equals", "Operands": ["CONFIRM"]},
            },
            {
                "NextAction": end,
                "Condition": {"Operator": "Equals", "Operands": ["END"]},
            },
            {
                "NextAction": handoff,
                "Condition": {"Operator": "Equals", "Operands": ["HANDOFF"]},
            },
            {
                "NextAction": listen,
                "Condition": {"Operator": "Equals", "Operands": ["LISTEN"]},
            },
        ],
        "Errors": [
            {"NextAction": listen, "ErrorType": "NoMatchingCondition"},
        ],
    }


def content() -> dict:
    return {
        "Version": "2019-10-30",
        "StartAction": ids["logging"],
        "Metadata": _meta(),
        "Actions": [
            {
                "Identifier": ids["logging"],
                "Type": "UpdateFlowLoggingBehavior",
                "Parameters": {"FlowLoggingBehavior": "Enabled"},
                "Transitions": {"NextAction": ids["set_voice"], "Errors": []},
            },
            {
                "Identifier": ids["set_voice"],
                "Type": "UpdateContactTextToSpeechVoice",
                "Parameters": {"TextToSpeechVoice": "Mizuki"},
                "Transitions": {
                    "NextAction": ids["resolve"],
                    "Errors": [
                        {"NextAction": ids["resolve"], "ErrorType": "NoMatchingError"}
                    ],
                },
            },
            {
                "Identifier": ids["resolve"],
                "Type": "InvokeLambdaFunction",
                "Parameters": {
                    "LambdaFunctionARN": LAMBDA_RESOLVE,
                    "InvocationTimeLimitSeconds": "8",
                    "InvocationType": "SYNCHRONOUS",
                    "ResponseValidation": {"ResponseType": "STRING_MAP"},
                },
                "Transitions": {
                    "NextAction": ids["set_resolve"],
                    "Errors": [
                        {"NextAction": ids["unknown"], "ErrorType": "NoMatchingError"}
                    ],
                },
            },
            {
                "Identifier": ids["set_resolve"],
                "Type": "UpdateContactAttributes",
                "Parameters": {
                    "Attributes": {
                        "found": "$.External.found",
                        "callType": "$.External.callType",
                        "tenantId": "$.External.tenantId",
                        "storeName": "$.External.storeName",
                        "menuPrompt": "$.External.menuPrompt",
                        "inboundId": "$.External.inboundId",
                        "callerNumber": "$.External.callerNumber",
                        "callerNumberAvailable": "$.External.callerNumberAvailable",
                        "inboundIsDemo": "$.External.inboundIsDemo",
                        "callerNumberIsDemo": "$.External.callerNumberIsDemo",
                        "transferPhoneNumber": "$.External.transferPhoneNumber",
                        # dialog seed (Connect owns the loop)
                        "step": "party_size",
                        "phase": "collect",
                        "date": " ",
                        "time": " ",
                        "partySize": " ",
                        "name": " ",
                        "lastPrompt": " ",
                        "resultStatus": " ",
                        "reservationId": " ",
                        "prompt": PARTY_PROMPT,
                        "aiResponseText": PARTY_PROMPT,
                        "routingAction": "LISTEN",
                        "action": "listen",
                    },
                    "TargetContact": "Current",
                },
                "Transitions": {
                    "NextAction": ids["check_found"],
                    "Errors": [
                        {"NextAction": ids["unknown"], "ErrorType": "NoMatchingError"}
                    ],
                },
            },
            {
                "Identifier": ids["check_found"],
                "Type": "Compare",
                "Parameters": {"ComparisonValue": "$.Attributes.found"},
                "Transitions": {
                    "NextAction": ids["unknown"],
                    "Conditions": [
                        {
                            "NextAction": ids["greet"],
                            "Condition": {
                                "Operator": "Equals",
                                "Operands": ["true"],
                            },
                        }
                    ],
                    "Errors": [
                        {
                            "NextAction": ids["unknown"],
                            "ErrorType": "NoMatchingCondition",
                        }
                    ],
                },
            },
            {
                "Identifier": ids["unknown"],
                "Type": "MessageParticipant",
                "Parameters": {
                    "Text": (
                        "申し訳ありません。店舗を特定できませんでした。"
                        "電話番号をご確認のうえ、再度おかけ直しください。"
                    )
                },
                "Transitions": {"NextAction": ids["bye"], "Errors": []},
            },
            {
                "Identifier": ids["greet"],
                "Type": "MessageParticipant",
                "Parameters": {"Text": "$.Attributes.menuPrompt"},
                "Transitions": {
                    "NextAction": ids["ask_party"],
                    "Errors": [
                        {
                            "NextAction": ids["ask_party"],
                            "ErrorType": "NoMatchingError",
                        }
                    ],
                },
            },
            {
                "Identifier": ids["ask_party"],
                "Type": "MessageParticipant",
                "Parameters": {"Text": PARTY_PROMPT},
                "Transitions": {
                    "NextAction": ids["lex"],
                    "Errors": [
                        {"NextAction": ids["lex"], "ErrorType": "NoMatchingError"}
                    ],
                },
            },
            {
                # Text " " → Lex は聞き取り専用（Helpdesk と同じ）
                "Identifier": ids["lex"],
                "Type": "ConnectParticipantWithLexBot",
                "Parameters": {
                    "Text": " ",
                    "LexV2Bot": {"AliasArn": LEX_ALIAS},
                    "LexSessionAttributes": _lex_session_from_attrs(),
                },
                "Transitions": {
                    "NextAction": ids["copy_lex"],
                    "Errors": [
                        {
                            "NextAction": ids["copy_lex"],
                            "ErrorType": "NoMatchingCondition",
                        },
                        {
                            "NextAction": ids["copy_lex"],
                            "ErrorType": "NoMatchingError",
                        },
                    ],
                },
            },
            {
                "Identifier": ids["copy_lex"],
                "Type": "UpdateContactAttributes",
                "Parameters": {
                    "Attributes": _copy_lex_to_attrs(),
                    "TargetContact": "Current",
                },
                "Transitions": {
                    "NextAction": ids["branch"],
                    "Errors": [
                        {"NextAction": ids["branch"], "ErrorType": "NoMatchingError"}
                    ],
                },
            },
            {
                "Identifier": ids["branch"],
                "Type": "Compare",
                "Parameters": {
                    "ComparisonValue": "$.Attributes.routingAction"
                },
                "Transitions": _branch_transitions(
                    listen=ids["play_listen"],
                    confirm=ids["play_confirm"],
                    end=ids["play_end"],
                    handoff=ids["play_handoff"],
                ),
            },
            {
                "Identifier": ids["play_listen"],
                "Type": "MessageParticipant",
                "Parameters": {"Text": "$.Attributes.aiResponseText"},
                "Transitions": {
                    "NextAction": ids["lex"],
                    "Errors": [
                        {"NextAction": ids["lex"], "ErrorType": "NoMatchingError"}
                    ],
                },
            },
            {
                "Identifier": ids["play_confirm"],
                "Type": "MessageParticipant",
                "Parameters": {"Text": "$.Attributes.aiResponseText"},
                "Transitions": {
                    "NextAction": ids["dtmf_confirm"],
                    "Errors": [
                        {
                            "NextAction": ids["dtmf_confirm"],
                            "ErrorType": "NoMatchingError",
                        }
                    ],
                },
            },
            {
                "Identifier": ids["dtmf_confirm"],
                "Type": "GetParticipantInput",
                "Parameters": {
                    # Helpdesk と同じ: DTMF 分岐は StoreInput=False。
                    # True だと InputValidation 必須になり Conditions が使えない。
                    "StoreInput": "False",
                    "InputTimeLimitSeconds": "10",
                    "Text": "よろしければ1を、訂正する場合は2を押してください。",
                },
                "Transitions": {
                    "NextAction": ids["play_confirm"],
                    "Conditions": [
                        {
                            "NextAction": ids["set_dtmf_1"],
                            "Condition": {
                                "Operator": "Equals",
                                "Operands": ["1"],
                            },
                        },
                        {
                            "NextAction": ids["set_dtmf_2"],
                            "Condition": {
                                "Operator": "Equals",
                                "Operands": ["2"],
                            },
                        },
                    ],
                    "Errors": [
                        {
                            "NextAction": ids["play_confirm"],
                            "ErrorType": "InputTimeLimitExceeded",
                        },
                        {
                            "NextAction": ids["play_confirm"],
                            "ErrorType": "NoMatchingCondition",
                        },
                        {
                            "NextAction": ids["handoff"],
                            "ErrorType": "NoMatchingError",
                        },
                    ],
                },
            },
            {
                "Identifier": ids["set_dtmf_1"],
                "Type": "UpdateContactAttributes",
                "Parameters": {
                    "Attributes": {"dtmf": "1"},
                    "TargetContact": "Current",
                },
                "Transitions": {
                    "NextAction": ids["invoke_turn"],
                    "Errors": [
                        {
                            "NextAction": ids["invoke_turn"],
                            "ErrorType": "NoMatchingError",
                        }
                    ],
                },
            },
            {
                "Identifier": ids["set_dtmf_2"],
                "Type": "UpdateContactAttributes",
                "Parameters": {
                    "Attributes": {"dtmf": "2"},
                    "TargetContact": "Current",
                },
                "Transitions": {
                    "NextAction": ids["invoke_turn"],
                    "Errors": [
                        {
                            "NextAction": ids["invoke_turn"],
                            "ErrorType": "NoMatchingError",
                        }
                    ],
                },
            },
            {
                "Identifier": ids["invoke_turn"],
                "Type": "InvokeLambdaFunction",
                "Parameters": {
                    "LambdaFunctionARN": LAMBDA_TURN,
                    "InvocationTimeLimitSeconds": "8",
                    "InvocationType": "SYNCHRONOUS",
                    "ResponseValidation": {"ResponseType": "STRING_MAP"},
                },
                "Transitions": {
                    "NextAction": ids["copy_turn"],
                    "Errors": [
                        {"NextAction": ids["handoff"], "ErrorType": "NoMatchingError"}
                    ],
                },
            },
            {
                "Identifier": ids["copy_turn"],
                "Type": "UpdateContactAttributes",
                "Parameters": {
                    "Attributes": _copy_external_to_attrs(),
                    "TargetContact": "Current",
                },
                "Transitions": {
                    "NextAction": ids["branch_turn"],
                    "Errors": [
                        {
                            "NextAction": ids["branch_turn"],
                            "ErrorType": "NoMatchingError",
                        }
                    ],
                },
            },
            {
                "Identifier": ids["branch_turn"],
                "Type": "Compare",
                "Parameters": {
                    "ComparisonValue": "$.Attributes.routingAction"
                },
                "Transitions": _branch_transitions(
                    listen=ids["play_listen"],
                    confirm=ids["play_confirm"],
                    end=ids["play_end"],
                    handoff=ids["play_handoff"],
                ),
            },
            {
                "Identifier": ids["play_end"],
                "Type": "MessageParticipant",
                "Parameters": {"Text": "$.Attributes.aiResponseText"},
                "Transitions": {
                    "NextAction": ids["thanks"],
                    "Errors": [
                        {"NextAction": ids["thanks"], "ErrorType": "NoMatchingError"}
                    ],
                },
            },
            {
                "Identifier": ids["thanks"],
                "Type": "MessageParticipant",
                "Parameters": {"Text": "お電話ありがとうございました。"},
                "Transitions": {"NextAction": ids["bye"], "Errors": []},
            },
            {
                "Identifier": ids["play_handoff"],
                "Type": "MessageParticipant",
                "Parameters": {"Text": "$.Attributes.aiResponseText"},
                "Transitions": {
                    "NextAction": ids["handoff"],
                    "Errors": [
                        {"NextAction": ids["handoff"], "ErrorType": "NoMatchingError"}
                    ],
                },
            },
            {
                "Identifier": ids["handoff"],
                "Type": "MessageParticipant",
                "Parameters": {
                    "Text": (
                        "申し訳ありません。担当者への引き継ぎはこれから接続します。"
                        "いったん通話を終了します。"
                    )
                },
                "Transitions": {"NextAction": ids["bye"], "Errors": []},
            },
            {
                "Identifier": ids["bye"],
                "Type": "DisconnectParticipant",
                "Parameters": {},
                "Transitions": {},
            },
        ],
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(content(), ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

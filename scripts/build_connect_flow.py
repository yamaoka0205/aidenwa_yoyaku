#!/usr/bin/env python3
"""Write infra/connect/BookingApp-Inbound.flow.json with placeholders."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "infra" / "connect" / "BookingApp-Inbound.flow.json"

LAMBDA_RESOLVE = (
    "arn:aws:lambda:${AWS_DEFAULT_REGION}:${AWS_ACCOUNT_ID}:function:BookingAppResolveStore"
)
LEX_ALIAS = (
    "arn:aws:lex:${AWS_DEFAULT_REGION}:${AWS_ACCOUNT_ID}:bot-alias/"
    "${LEX_BOT_ID}/${LEX_ALIAS_ID}"
)

ids = {
    "set_voice": "11111111-1111-4111-8111-111111111101",
    "invoke": "11111111-1111-4111-8111-111111111102",
    "set_attrs": "11111111-1111-4111-8111-111111111103",
    "check_found": "11111111-1111-4111-8111-111111111104",
    "menu_greet": "11111111-1111-4111-8111-111111111113",
    "menu": "11111111-1111-4111-8111-111111111105",
    "menu_retry": "11111111-1111-4111-8111-111111111106",
    "lex_reserve": "11111111-1111-4111-8111-111111111107",
    "lex_faq": "11111111-1111-4111-8111-111111111108",
    "unknown": "11111111-1111-4111-8111-111111111109",
    "handoff": "11111111-1111-4111-8111-111111111110",
    "bye": "11111111-1111-4111-8111-111111111111",
    "after_lex": "11111111-1111-4111-8111-111111111112",
}

MENU_DTMF_TEXT = (
    "ご予約の方は1を、それ以外のお問い合わせは2を押してください。"
)


def content() -> dict:
    return {
        "Version": "2019-10-30",
        "StartAction": ids["set_voice"],
        "Metadata": {
            "EntryPointPosition": {"x": 40, "y": 40},
            "ActionMetadata": {
                i: {"Position": {"x": 160 + (n % 5) * 240, "y": 40 + (n // 5) * 180}}
                for n, i in enumerate(ids.values())
            },
        },
        "Actions": [
            {
                "Identifier": ids["set_voice"],
                "Type": "UpdateContactTextToSpeechVoice",
                "Parameters": {"TextToSpeechVoice": "Mizuki"},
                "Transitions": {
                    "NextAction": ids["invoke"],
                    "Errors": [
                        {"NextAction": ids["invoke"], "ErrorType": "NoMatchingError"}
                    ],
                },
            },
            {
                "Identifier": ids["invoke"],
                "Type": "InvokeLambdaFunction",
                "Parameters": {
                    "LambdaFunctionARN": LAMBDA_RESOLVE,
                    "InvocationTimeLimitSeconds": "8",
                    "InvocationType": "SYNCHRONOUS",
                    "ResponseValidation": {"ResponseType": "STRING_MAP"},
                },
                "Transitions": {
                    "NextAction": ids["set_attrs"],
                    "Errors": [
                        {"NextAction": ids["unknown"], "ErrorType": "NoMatchingError"}
                    ],
                },
            },
            {
                "Identifier": ids["set_attrs"],
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
                            "NextAction": ids["menu_greet"],
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
                # Play store greeting alone. GetParticipantInput Text must stay
                # static — attribute-only Text broke DTMF "1" → Lex on WebRTC.
                "Identifier": ids["menu_greet"],
                "Type": "MessageParticipant",
                "Parameters": {"Text": "$.Attributes.menuPrompt"},
                "Transitions": {
                    "NextAction": ids["menu"],
                    "Errors": [
                        {
                            "NextAction": ids["menu"],
                            "ErrorType": "NoMatchingError",
                        }
                    ],
                },
            },
            {
                "Identifier": ids["menu"],
                "Type": "GetParticipantInput",
                "Parameters": {
                    "StoreInput": "False",
                    "InputTimeLimitSeconds": "10",
                    "Text": MENU_DTMF_TEXT,
                },
                "Transitions": {
                    "NextAction": ids["menu_retry"],
                    "Conditions": [
                        {
                            "NextAction": ids["lex_reserve"],
                            "Condition": {
                                "Operator": "Equals",
                                "Operands": ["1"],
                            },
                        },
                        {
                            "NextAction": ids["lex_faq"],
                            "Condition": {
                                "Operator": "Equals",
                                "Operands": ["2"],
                            },
                        },
                    ],
                    "Errors": [
                        {
                            "NextAction": ids["menu_retry"],
                            "ErrorType": "InputTimeLimitExceeded",
                        },
                        {
                            "NextAction": ids["menu_retry"],
                            "ErrorType": "NoMatchingCondition",
                        },
                        {
                            "NextAction": ids["menu_retry"],
                            "ErrorType": "NoMatchingError",
                        },
                    ],
                },
            },
            {
                "Identifier": ids["menu_retry"],
                "Type": "GetParticipantInput",
                "Parameters": {
                    "StoreInput": "False",
                    "InputTimeLimitSeconds": "10",
                    "Text": "もう一度お願いします。" + MENU_DTMF_TEXT,
                },
                "Transitions": {
                    "NextAction": ids["handoff"],
                    "Conditions": [
                        {
                            "NextAction": ids["lex_reserve"],
                            "Condition": {
                                "Operator": "Equals",
                                "Operands": ["1"],
                            },
                        },
                        {
                            "NextAction": ids["lex_faq"],
                            "Condition": {
                                "Operator": "Equals",
                                "Operands": ["2"],
                            },
                        },
                    ],
                    "Errors": [
                        {
                            "NextAction": ids["handoff"],
                            "ErrorType": "InputTimeLimitExceeded",
                        },
                        {
                            "NextAction": ids["handoff"],
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
                "Identifier": ids["lex_reserve"],
                "Type": "ConnectParticipantWithLexBot",
                "Parameters": {
                    "Text": "人数は何人ですか。1から6の数字でお答えください。ボタンでも入力できます。",
                    "LexV2Bot": {"AliasArn": LEX_ALIAS},
                    "LexSessionAttributes": {
                        "tenantId": "$.Attributes.tenantId",
                        "callerNumber": "$.Attributes.callerNumber",
                        "callerNumberAvailable": "$.Attributes.callerNumberAvailable",
                        "storeName": "$.Attributes.storeName",
                        "intentHint": "BookReservation",
                    },
                },
                # Intent name is the result. Without Conditions, Connect treats
                # BookReservation / FallbackIntent as NoMatchingCondition → handoff.
                "Transitions": {
                    "NextAction": ids["after_lex"],
                    "Conditions": [
                        {
                            "NextAction": ids["after_lex"],
                            "Condition": {
                                "Operator": "Equals",
                                "Operands": ["BookReservation"],
                            },
                        },
                        {
                            "NextAction": ids["after_lex"],
                            "Condition": {
                                "Operator": "Equals",
                                "Operands": ["FallbackIntent"],
                            },
                        },
                    ],
                    "Errors": [
                        {
                            "NextAction": ids["after_lex"],
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
                "Identifier": ids["lex_faq"],
                "Type": "ConnectParticipantWithLexBot",
                "Parameters": {
                    "Text": "ご用件をお話しください。",
                    "LexV2Bot": {"AliasArn": LEX_ALIAS},
                    "LexSessionAttributes": {
                        "tenantId": "$.Attributes.tenantId",
                        "storeName": "$.Attributes.storeName",
                        "intentHint": "AskFaq",
                    },
                },
                "Transitions": {
                    "NextAction": ids["after_lex"],
                    "Conditions": [
                        {
                            "NextAction": ids["after_lex"],
                            "Condition": {
                                "Operator": "Equals",
                                "Operands": ["AskFaq"],
                            },
                        },
                        {
                            "NextAction": ids["after_lex"],
                            "Condition": {
                                "Operator": "Equals",
                                "Operands": ["FallbackIntent"],
                            },
                        },
                    ],
                    "Errors": [
                        {
                            "NextAction": ids["after_lex"],
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
                "Identifier": ids["after_lex"],
                "Type": "MessageParticipant",
                "Parameters": {"Text": "お電話ありがとうございました。"},
                "Transitions": {"NextAction": ids["bye"], "Errors": []},
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

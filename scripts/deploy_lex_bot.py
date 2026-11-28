#!/usr/bin/env python3
"""Create/update Lex V2 bot BookingAppPhone (ja_JP) with Lambda code hooks."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
BOT_NAME = "BookingAppPhone"
LOCALE = "ja_JP"
ALIAS_NAME = "live"
ROLE_NAME = "BookingAppLexRole"
INSTANCE_ID = os.environ.get(
    "CONNECT_INSTANCE_ID", "98c809c0-0dd7-414f-979a-bf7816f5bfae"
)
OUT = ROOT / "build" / "lex_bot.json"

TRUST = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lexv2.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}


def wait_bot(lex, bot_id: str, status: str = "Available", timeout: int = 180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        desc = lex.describe_bot(botId=bot_id)
        st = desc.get("botStatus")
        print(f"  botStatus={st}")
        if st == status:
            return desc
        if st == "Failed":
            raise RuntimeError(desc.get("failureReasons"))
        time.sleep(5)
    raise TimeoutError(f"bot not {status}")


def wait_locale(lex, bot_id: str, locale_id: str, status: str = "Built", timeout: int = 300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        desc = lex.describe_bot_locale(botId=bot_id, botVersion="DRAFT", localeId=locale_id)
        st = desc.get("botLocaleStatus")
        print(f"  localeStatus={st}")
        if st == status:
            return desc
        if st == "Failed":
            raise RuntimeError(desc.get("failureReasons"))
        time.sleep(5)
    raise TimeoutError(f"locale not {status}")


def ensure_lex_role(iam, account: str) -> str:
    role_arn = f"arn:aws:iam::{account}:role/{ROLE_NAME}"
    try:
        iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(TRUST),
            Description="Lex V2 execution role for BookingAppPhone",
        )
        print(f"Created role {ROLE_NAME}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        print(f"Role exists {ROLE_NAME}")
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="BookingAppLexInline",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "polly:SynthesizeSpeech",
                            "comprehend:DetectSentiment",
                        ],
                        "Resource": "*",
                    }
                ],
            }
        ),
    )
    # Lex needs a moment after role create
    time.sleep(10)
    return role_arn


def find_bot(lex, name: str) -> str | None:
    token = None
    while True:
        kwargs = {"maxResults": 50}
        if token:
            kwargs["nextToken"] = token
        resp = lex.list_bots(**kwargs)
        for b in resp.get("botSummaries", []):
            if b["botName"] == name:
                return b["botId"]
        token = resp.get("nextToken")
        if not token:
            return None


def main() -> int:
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    if not region:
        print("ERROR: set AWS_DEFAULT_REGION", file=sys.stderr)
        return 1
    session = boto3.Session(region_name=region)
    sts = session.client("sts")
    iam = session.client("iam")
    lex = session.client("lexv2-models")
    lam = session.client("lambda")
    connect = session.client("connect")
    account = sts.get_caller_identity()["Account"]

    router_arn = lam.get_function(FunctionName="BookingAppPhoneTurn")["Configuration"][
        "FunctionArn"
    ]

    role_arn = ensure_lex_role(iam, account)

    bot_id = find_bot(lex, BOT_NAME)
    if not bot_id:
        resp = lex.create_bot(
            botName=BOT_NAME,
            description="BookingApp phone dialog (reserve + FAQ)",
            roleArn=role_arn,
            dataPrivacy={"childDirected": False},
            idleSessionTTLInSeconds=300,
        )
        bot_id = resp["botId"]
        print(f"Created bot {bot_id}")
        wait_bot(lex, bot_id)
    else:
        print(f"Bot exists {bot_id}")

    # Locale
    try:
        lex.create_bot_locale(
            botId=bot_id,
            botVersion="DRAFT",
            localeId=LOCALE,
            nluIntentConfidenceThreshold=0.4,
            voiceSettings={"voiceId": "Mizuki", "engine": "standard"},
        )
        print(f"Created locale {LOCALE}")
        time.sleep(5)
    except ClientError as exc:
        # ConflictException or PreconditionFailedException when locale already exists
        if exc.response["Error"]["Code"] not in {
            "ConflictException",
            "PreconditionFailedException",
        }:
            raise
        print(f"Locale exists {LOCALE}")

    # Intents
    intents = lex.list_intents(botId=bot_id, botVersion="DRAFT", localeId=LOCALE).get(
        "intentSummaries", []
    )
    by_name = {i["intentName"]: i["intentId"] for i in intents}

    fulfillment = {
        "enabled": True,
        "active": True,
        "postFulfillmentStatusSpecification": {
            "successNextStep": {"dialogAction": {"type": "EndConversation"}},
            "failureNextStep": {"dialogAction": {"type": "EndConversation"}},
            "timeoutNextStep": {"dialogAction": {"type": "EndConversation"}},
        },
    }

    def upsert_intent(
        name: str,
        samples: list[str],
        dialog: bool,
        slot_priorities: list[dict] | None = None,
    ):
        # Lex locale build requires ≥1 utterance + slot priorities. Field
        # collection still goes through FallbackIntent → Lambda (ASR/TTS only).
        payload = {
            "botId": bot_id,
            "botVersion": "DRAFT",
            "localeId": LOCALE,
            "intentName": name,
            "sampleUtterances": [{"utterance": u} for u in samples],
            "fulfillmentCodeHook": fulfillment,
        }
        if dialog:
            payload["dialogCodeHook"] = {"enabled": True}
        if slot_priorities:
            payload["slotPriorities"] = slot_priorities
        if name in by_name:
            lex.update_intent(intentId=by_name[name], **payload)
            print(f"Updated intent {name}")
            return by_name[name]
        resp = lex.create_intent(**payload)
        print(f"Created intent {name} {resp['intentId']}")
        return resp["intentId"]

    # Placeholder utterances only so locale build succeeds (not for dialog NLU).
    book_id = upsert_intent("BookReservation", ["予約"], dialog=True)
    faq_id = upsert_intent("AskFaq", ["質問"], dialog=True)

    def ensure_freeform_slot(intent_id: str, slot_name: str) -> str:
        """AMAZON.FreeFormInput keeps the next turn on DialogCodeHook (no NLU)."""
        existing = {
            s["slotName"]: s["slotId"]
            for s in lex.list_slots(
                botId=bot_id, botVersion="DRAFT", localeId=LOCALE, intentId=intent_id
            ).get("slotSummaries", [])
        }
        body = {
            "slotTypeId": "AMAZON.FreeFormInput",
            "valueElicitationSetting": {
                "slotConstraint": "Optional",
                "promptSpecification": {
                    "messageGroups": [
                        {
                            "message": {
                                "plainTextMessage": {"value": "続けてお話しください。"}
                            }
                        }
                    ],
                    "maxRetries": 2,
                    "allowInterrupt": True,
                },
            },
        }
        if slot_name in existing:
            lex.update_slot(
                slotId=existing[slot_name],
                slotName=slot_name,
                botId=bot_id,
                botVersion="DRAFT",
                localeId=LOCALE,
                intentId=intent_id,
                **body,
            )
            print(f"Updated slot {slot_name}")
            return existing[slot_name]
        resp = lex.create_slot(
            slotName=slot_name,
            botId=bot_id,
            botVersion="DRAFT",
            localeId=LOCALE,
            intentId=intent_id,
            **body,
        )
        print(f"Created slot {slot_name}")
        return resp["slotId"]

    book_user = ensure_freeform_slot(book_id, "UserReply")
    book_confirm = ensure_freeform_slot(book_id, "Confirmation")
    faq_user = ensure_freeform_slot(faq_id, "UserReply")

    # Re-save intents with slot priorities (required after creating slots).
    upsert_intent(
        "BookReservation",
        ["予約"],
        dialog=True,
        slot_priorities=[
            {"priority": 1, "slotId": book_user},
            {"priority": 2, "slotId": book_confirm},
        ],
    )
    upsert_intent(
        "AskFaq",
        ["質問"],
        dialog=True,
        slot_priorities=[{"priority": 1, "slotId": faq_user}],
    )

    # Short ASR results ("4", "明日") hit FallbackIntent. Hook it to the same Lambda
    # so Connect does not treat Fallback as end-of-call.
    fb_id = by_name.get("FallbackIntent")
    if not fb_id:
        intents = lex.list_intents(
            botId=bot_id, botVersion="DRAFT", localeId=LOCALE
        ).get("intentSummaries", [])
        fb_id = next(
            (i["intentId"] for i in intents if i["intentName"] == "FallbackIntent"),
            None,
        )
    if fb_id:
        lex.update_intent(
            intentId=fb_id,
            botId=bot_id,
            botVersion="DRAFT",
            localeId=LOCALE,
            intentName="FallbackIntent",
            parentIntentSignature="AMAZON.FallbackIntent",
            dialogCodeHook={"enabled": True},
            fulfillmentCodeHook=fulfillment,
        )
        print("Updated FallbackIntent code hooks")
    else:
        print("WARN: FallbackIntent not found — short answers may disconnect")

    # Attach Lambda code hooks via bot alias / bot locale resource — Lex V2 uses
    # bot aliases' botAliasLocaleSettings with codeHookSpecification, AND
    # intent-level code hooks need Lambda permission + alias association.
    # Build locale first, then create version + alias with lambda code hook.
    print("Building locale...")
    lex.build_bot_locale(botId=bot_id, botVersion="DRAFT", localeId=LOCALE)
    wait_locale(lex, bot_id, LOCALE, status="Built")

    # Create version from DRAFT
    ver = lex.create_bot_version(
        botId=bot_id,
        botVersionLocaleSpecification={LOCALE: {"sourceBotVersion": "DRAFT"}},
    )
    version = ver["botVersion"]
    print(f"Created version {version}")
    # wait version available
    for _ in range(36):
        d = lex.describe_bot_version(botId=bot_id, botVersion=version)
        if d.get("botStatus") == "Available":
            break
        time.sleep(5)
    else:
        raise TimeoutError("bot version not available")

    # Lambda permissions for Lex
    source_arn = f"arn:aws:lex:{region}:{account}:bot-alias/{bot_id}/*"
    try:
        lam.add_permission(
            FunctionName="BookingAppPhoneTurn",
            StatementId="LexBookingAppPhoneTurn",
            Action="lambda:InvokeFunction",
            Principal="lexv2.amazonaws.com",
            SourceArn=source_arn,
            SourceAccount=account,
        )
        print("Permission LexBookingAppPhoneTurn")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceConflictException":
            raise
        print("Permission exists LexBookingAppPhoneTurn")

    # Alias
    aliases = lex.list_bot_aliases(botId=bot_id).get("botAliasSummaries", [])
    alias = next((a for a in aliases if a["botAliasName"] == ALIAS_NAME), None)
    locale_settings = {
        LOCALE: {
            "enabled": True,
            "codeHookSpecification": {
                "lambdaCodeHook": {
                    "lambdaARN": router_arn,
                    "codeHookInterfaceVersion": "1.0",
                }
            },
        }
    }

    if alias:
        lex.update_bot_alias(
            botAliasId=alias["botAliasId"],
            botAliasName=ALIAS_NAME,
            botId=bot_id,
            botVersion=version,
            botAliasLocaleSettings=locale_settings,
            sentimentAnalysisSettings={"detectSentiment": False},
        )
        alias_id = alias["botAliasId"]
        print(f"Updated alias {alias_id}")
    else:
        resp = lex.create_bot_alias(
            botAliasName=ALIAS_NAME,
            botId=bot_id,
            botVersion=version,
            botAliasLocaleSettings=locale_settings,
            sentimentAnalysisSettings={"detectSentiment": False},
        )
        alias_id = resp["botAliasId"]
        print(f"Created alias {alias_id}")

    alias_arn = f"arn:aws:lex:{region}:{account}:bot-alias/{bot_id}/{alias_id}"

    # Associate Lex bot with Connect
    try:
        connect.associate_lex_bot(
            InstanceId=INSTANCE_ID,
            LexBot={"Name": BOT_NAME, "LexRegion": region},
        )
    except Exception:
        pass
    try:
        connect.associate_bot(
            InstanceId=INSTANCE_ID,
            LexV2Bot={"AliasArn": alias_arn},
        )
        print("Associated Lex V2 bot with Connect")
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {
            "ResourceConflictException",
            "DuplicateResourceException",
        }:
            # older API shape
            print(f"associate_bot: {exc.response['Error']['Code']} {exc.response['Error']['Message'][:160]}")
        else:
            print("Lex bot already associated with Connect")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "botName": BOT_NAME,
        "botId": bot_id,
        "aliasName": ALIAS_NAME,
        "aliasId": alias_id,
        "aliasArn": alias_arn,
        "locale": LOCALE,
        "version": version,
    }
    OUT.write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClientError as exc:
        print(
            f"ERROR [{exc.response['Error']['Code']}]: {exc.response['Error']['Message']}",
            file=sys.stderr,
        )
        raise SystemExit(1)

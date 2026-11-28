#!/usr/bin/env python3
"""Create or update the BookingApp-Inbound Connect contact flow."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
FLOW_PATH = ROOT / "infra" / "connect" / "BookingApp-Inbound.flow.json"
LEX_META = ROOT / "build" / "lex_bot.json"
FLOW_NAME = "BookingApp-Inbound"
INSTANCE_ID = os.environ.get(
    "CONNECT_INSTANCE_ID", "98c809c0-0dd7-414f-979a-bf7816f5bfae"
)
PLACEHOLDER_RESOLVE = (
    "arn:aws:lambda:${AWS_DEFAULT_REGION}:${AWS_ACCOUNT_ID}:function:BookingAppResolveStore"
)
PLACEHOLDER_TURN = (
    "arn:aws:lambda:${AWS_DEFAULT_REGION}:${AWS_ACCOUNT_ID}"
    ":function:BookingAppReservationTurn"
)
PLACEHOLDER_LEX = (
    "arn:aws:lex:${AWS_DEFAULT_REGION}:${AWS_ACCOUNT_ID}:bot-alias/"
    "${LEX_BOT_ID}/${LEX_ALIAS_ID}"
)


def _associate_lambda(connect, lam, *, instance_id: str, function_name: str) -> str:
    fn_arn = lam.get_function(FunctionName=function_name)["Configuration"][
        "FunctionArn"
    ]
    try:
        connect.associate_lambda_function(InstanceId=instance_id, FunctionArn=fn_arn)
        print(f"Associated {fn_arn}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceConflictException":
            raise
        print(f"Lambda already associated: {function_name}")
    return fn_arn


def _permit_connect(lam, *, function_name: str, account: str, region: str) -> None:
    instance_arn = f"arn:aws:connect:{region}:{account}:instance/{INSTANCE_ID}"
    sid = f"AmazonConnect{function_name}"
    try:
        lam.add_permission(
            FunctionName=function_name,
            StatementId=sid,
            Action="lambda:InvokeFunction",
            Principal="connect.amazonaws.com",
            SourceAccount=account,
            SourceArn=instance_arn,
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceConflictException":
            raise


def main() -> int:
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    if not region:
        print("ERROR: set AWS_DEFAULT_REGION", file=sys.stderr)
        return 1

    from build_connect_flow import main as build_template

    build_template()

    session = boto3.Session(region_name=region)
    sts = session.client("sts")
    lam = session.client("lambda")
    connect = session.client("connect")
    account = sts.get_caller_identity()["Account"]

    if not LEX_META.exists():
        print(
            f"ERROR: {LEX_META} missing. Run scripts/deploy_lex_bot.py first.",
            file=sys.stderr,
        )
        return 1
    lex = json.loads(LEX_META.read_text())
    lex_arn = lex["aliasArn"]

    resolve_arn = _associate_lambda(
        connect, lam, instance_id=INSTANCE_ID, function_name="BookingAppResolveStore"
    )
    turn_arn = _associate_lambda(
        connect,
        lam,
        instance_id=INSTANCE_ID,
        function_name="BookingAppReservationTurn",
    )

    try:
        connect.associate_bot(InstanceId=INSTANCE_ID, LexV2Bot={"AliasArn": lex_arn})
        print("Associated Lex bot")
    except ClientError as exc:
        print(f"associate_bot: {exc.response['Error']['Code']}")

    _permit_connect(
        lam, function_name="BookingAppResolveStore", account=account, region=region
    )
    _permit_connect(
        lam,
        function_name="BookingAppReservationTurn",
        account=account,
        region=region,
    )

    raw = FLOW_PATH.read_text()
    raw = (
        raw.replace(PLACEHOLDER_RESOLVE, resolve_arn)
        .replace(PLACEHOLDER_TURN, turn_arn)
        .replace(PLACEHOLDER_LEX, lex_arn)
    )
    # Legacy single placeholder still present in older templates.
    raw = raw.replace(
        "arn:aws:lambda:${AWS_DEFAULT_REGION}:${AWS_ACCOUNT_ID}:function:BookingAppResolveStore",
        resolve_arn,
    )
    if "${" in raw:
        print("ERROR: unresolved placeholders remain", file=sys.stderr)
        return 1
    content = json.loads(raw)
    body = json.dumps(content)

    existing = connect.list_contact_flows(InstanceId=INSTANCE_ID).get(
        "ContactFlowSummaryList", []
    )
    match = next((f for f in existing if f["Name"] == FLOW_NAME), None)
    if match:
        connect.update_contact_flow_content(
            InstanceId=INSTANCE_ID, ContactFlowId=match["Id"], Content=body
        )
        flow_id = match["Id"]
        print(f"Updated {FLOW_NAME} ({flow_id})")
    else:
        resp = connect.create_contact_flow(
            InstanceId=INSTANCE_ID,
            Name=FLOW_NAME,
            Type="CONTACT_FLOW",
            Description=(
                "BookingApp inbound: ResolveStore → Lex ASR → Connect routing "
                "(Helpdesk-style)"
            ),
            Content=body,
        )
        flow_id = resp["ContactFlowId"]
        print(f"Created {FLOW_NAME} ({flow_id})")

    desc = connect.describe_contact_flow(InstanceId=INSTANCE_ID, ContactFlowId=flow_id)
    cf = desc["ContactFlow"]
    print(f"State={cf.get('State')} Status={cf.get('Status')}")
    print(f"Arn={cf['Arn']}")
    print(f"LexAlias={lex_arn}")
    print(f"Resolve={resolve_arn}")
    print(f"Turn={turn_arn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Deploy Booking API to AWS Lambda (Function URL; API Gateway if permitted).

Requires IAM beyond DynamoDB: Lambda, IAM role create/pass, logs.
API Gateway is optional — if denied, public Function URLs are used instead.

Usage:
  python3 scripts/deploy_api.py
  python3 scripts/deploy_api.py --only BookingAppListReservations,BookingAppGetStore
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Progress lines appear immediately even when stdout is piped.
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
ROLE_NAME = "BookingAppLambdaRole"
POLICY_NAME = "BookingAppLambdaPolicy"
API_NAME = "BookingAppApi"
FUNCTIONS = {
    "BookingAppCheckAvailability": {
        "handler": "handlers.check_availability.handler",
        "route": "POST /availability/check",
        "key": "checkAvailability",
    },
    "BookingAppConfirmReservation": {
        "handler": "handlers.confirm_reservation.handler",
        "route": "POST /reservations/confirm",
        "key": "confirmReservation",
    },
    "BookingAppListReservations": {
        "handler": "handlers.list_reservations.handler",
        "route": "POST /reservations/list",
        "key": "listReservations",
    },
    "BookingAppGetStore": {
        "handler": "handlers.get_store.handler",
        "route": "POST /store/get",
        "key": "getStore",
    },
    "BookingAppUpdateStore": {
        "handler": "handlers.update_store.handler",
        "route": "POST /store/update",
        "key": "updateStore",
    },
    "BookingAppLogin": {
        "handler": "handlers.login.handler",
        "route": "POST /auth/login",
        "key": "login",
    },
    "BookingAppLogout": {
        "handler": "handlers.logout.handler",
        "route": "POST /auth/logout",
        "key": "logout",
    },
    "BookingAppAuthMe": {
        "handler": "handlers.auth_me.handler",
        "route": "POST /auth/me",
        "key": "authMe",
    },
    "BookingAppCreateApplication": {
        "handler": "handlers.create_application.handler",
        "route": "POST /applications/create",
        "key": "createApplication",
    },
    "BookingAppListApplications": {
        "handler": "handlers.list_applications.handler",
        "route": "POST /applications/list",
        "key": "listApplications",
    },
    "BookingAppReviewApplication": {
        "handler": "handlers.review_application.handler",
        "route": "POST /applications/review",
        "key": "reviewApplication",
    },
}
# Called only from the Connect flow; no public URL or API route.
CONNECT_FUNCTIONS = {
    "BookingAppResolveStore": {
        "handler": "handlers.resolve_store.handler",
    },
    "BookingAppReservationTurn": {
        "handler": "handlers.reservation_turn.handler",
    },
    "BookingAppFaqTurn": {
        "handler": "handlers.faq_turn.handler",
    },
    "BookingAppPhoneTurn": {
        "handler": "handlers.phone_turn.handler",
    },
}


def region() -> str:
    value = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    if not value:
        print("ERROR: set AWS_DEFAULT_REGION", file=sys.stderr)
        raise SystemExit(1)
    return value


def account_id(sts) -> str:
    return sts.get_caller_identity()["Account"]


def package_zip() -> Path:
    script = ROOT / "scripts" / "package_lambda.sh"
    out = subprocess.check_output(["bash", str(script)], text=True).strip()
    path = Path(out)
    if not path.exists():
        raise RuntimeError(f"zip not found: {path}")
    print(f"Packaged {path} ({path.stat().st_size} bytes)")
    return path


def ensure_role(iam, account: str, reg: str) -> str:
    role_arn = f"arn:aws:iam::{account}:role/{ROLE_NAME}"
    trust = (ROOT / "infra" / "lambda_trust_policy.json").read_text()
    policy_doc = (ROOT / "infra" / "lambda_dynamodb_policy.json").read_text()
    created = False
    try:
        iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=trust,
            Description="Execution role for BookingApp Lambda functions",
        )
        print(f"Created role {ROLE_NAME}")
        created = True
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        print(f"Role exists {ROLE_NAME}")

    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName=POLICY_NAME,
        PolicyDocument=policy_doc,
    )

    # New roles need a short propagation wait; existing ones do not.
    if created:
        print("Waiting 8s for new IAM role propagation…")
        time.sleep(8)
    return role_arn


def _wait_updated(lam, name: str) -> None:
    print(f"  waiting for {name}…", flush=True)
    waiter = lam.get_waiter("function_updated_v2")
    waiter.wait(
        FunctionName=name,
        WaiterConfig={"Delay": 2, "MaxAttempts": 60},
    )


def cognito_env() -> dict[str, str]:
    path = ROOT / "build" / "cognito.json"
    if not path.exists():
        return {
            "COGNITO_USER_POOL_ID": os.environ.get("COGNITO_USER_POOL_ID", ""),
            "COGNITO_CLIENT_ID": os.environ.get("COGNITO_CLIENT_ID", ""),
        }
    data = json.loads(path.read_text())
    return {
        "COGNITO_USER_POOL_ID": data.get("userPoolId")
        or os.environ.get("COGNITO_USER_POOL_ID", ""),
        "COGNITO_CLIENT_ID": data.get("clientId")
        or os.environ.get("COGNITO_CLIENT_ID", ""),
    }


def ensure_function(lam, name: str, handler: str, role_arn: str, zip_path: Path, reg: str):
    env_vars = {
        "BOOKING_TABLE_NAME": "BookingApp",
        "BEDROCK_MODEL_ID": os.environ.get(
            "BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0"
        ),
        **cognito_env(),
    }
    env = {"Variables": {k: v for k, v in env_vars.items() if v}}
    zip_bytes = zip_path.read_bytes()
    try:
        current = lam.get_function(FunctionName=name)["Configuration"]
        exists = True
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        exists = False
        current = {}

    if not exists:
        print(f"Creating function {name}")
        lam.create_function(
            FunctionName=name,
            Runtime="python3.12",
            Role=role_arn,
            Handler=handler,
            Code={"ZipFile": zip_bytes},
            Timeout=15,
            MemorySize=256,
            Environment=env,
            Description="BookingApp API",
        )
        waiter = lam.get_waiter("function_active_v2")
        waiter.wait(
            FunctionName=name,
            WaiterConfig={"Delay": 2, "MaxAttempts": 60},
        )
    else:
        print(f"Updating function code {name}")
        lam.update_function_code(FunctionName=name, ZipFile=zip_bytes)
        _wait_updated(lam, name)

        needs_config = (
            current.get("Handler") != handler
            or current.get("Runtime") != "python3.12"
            or current.get("Timeout") != 15
            or current.get("MemorySize") != 256
            or current.get("Role") != role_arn
            or (current.get("Environment") or {}).get("Variables") != env["Variables"]
        )
        if needs_config:
            print(f"Updating function config {name}")
            lam.update_function_configuration(
                FunctionName=name,
                Handler=handler,
                Runtime="python3.12",
                Timeout=15,
                MemorySize=256,
                Environment=env,
                Role=role_arn,
            )
            _wait_updated(lam, name)
        else:
            print(f"  config unchanged for {name}")

    return lam.get_function(FunctionName=name)["Configuration"]["FunctionArn"]


def _add_permission(lam, *, function_name: str, statement_id: str, **kwargs) -> None:
    try:
        lam.add_permission(
            FunctionName=function_name,
            StatementId=statement_id,
            **kwargs,
        )
        print(f"Added permission {statement_id} on {function_name}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceConflictException":
            raise
        print(f"Permission exists {statement_id} on {function_name}")


def ensure_function_urls(lam) -> dict[str, str]:
    """Public HTTPS endpoints without API Gateway."""
    urls: dict[str, str] = {}
    for fn_name, meta in FUNCTIONS.items():
        try:
            cfg = lam.create_function_url_config(
                FunctionName=fn_name,
                AuthType="NONE",
                Cors={
                    "AllowOrigins": ["*"],
                    "AllowMethods": ["POST"],
                    "AllowHeaders": ["content-type", "authorization"],
                },
            )
            print(f"Created Function URL for {fn_name}")
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ResourceConflictException":
                raise
            cfg = lam.get_function_url_config(FunctionName=fn_name)
            try:
                lam.update_function_url_config(
                    FunctionName=fn_name,
                    Cors={
                        "AllowOrigins": ["*"],
                        "AllowMethods": ["POST"],
                        "AllowHeaders": ["content-type", "authorization"],
                    },
                )
            except ClientError:
                pass
            print(f"Function URL exists for {fn_name}")

        _add_permission(
            lam,
            function_name=fn_name,
            statement_id="FunctionURLAllowPublicAccess",
            Action="lambda:InvokeFunctionUrl",
            Principal="*",
            FunctionUrlAuthType="NONE",
        )
        _add_permission(
            lam,
            function_name=fn_name,
            statement_id="FunctionURLAllowPublicInvoke",
            Action="lambda:InvokeFunction",
            Principal="*",
        )
        urls[meta["key"]] = cfg["FunctionUrl"].rstrip("/")
    return urls


def ensure_http_api(apigw, lam, account: str, reg: str) -> str:
    apis = apigw.get_apis().get("Items", [])
    api_id = None
    for api in apis:
        if api.get("Name") == API_NAME:
            api_id = api["ApiId"]
            break
    if not api_id:
        print(f"Creating HTTP API {API_NAME}")
        api_id = apigw.create_api(
            Name=API_NAME,
            ProtocolType="HTTP",
            CorsConfiguration={
                "AllowHeaders": ["content-type", "authorization"],
                "AllowMethods": ["POST", "OPTIONS"],
                "AllowOrigins": ["*"],
            },
        )["ApiId"]
    else:
        print(f"HTTP API exists {api_id}")
        try:
            apigw.update_api(
                ApiId=api_id,
                CorsConfiguration={
                    "AllowHeaders": ["content-type", "authorization"],
                    "AllowMethods": ["POST", "OPTIONS"],
                    "AllowOrigins": ["*"],
                },
            )
        except ClientError as exc:
            print(f"CORS update skipped: {exc.response['Error'].get('Code')}")

    try:
        apigw.create_stage(ApiId=api_id, StageName="prod", AutoDeploy=True)
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {
            "ConflictException",
            "BadRequestException",
        }:
            msg = exc.response["Error"].get("Message", "")
            if "already exists" not in msg.lower():
                try:
                    apigw.get_stage(ApiId=api_id, StageName="prod")
                except ClientError:
                    raise exc

    for fn_name, meta in FUNCTIONS.items():
        method, path = meta["route"].split(" ", 1)
        integration_uri = (
            f"arn:aws:apigateway:{reg}:lambda:path/2015-03-31/functions/"
            f"arn:aws:lambda:{reg}:{account}:function:{fn_name}/invocations"
        )

        integrations = apigw.get_integrations(ApiId=api_id).get("Items", [])
        integration_id = None
        for integ in integrations:
            if integ.get("IntegrationUri") == integration_uri:
                integration_id = integ["IntegrationId"]
                break
        if not integration_id:
            integration_id = apigw.create_integration(
                ApiId=api_id,
                IntegrationType="AWS_PROXY",
                IntegrationUri=integration_uri,
                PayloadFormatVersion="2.0",
                IntegrationMethod="POST",
            )["IntegrationId"]
            print(f"Created integration for {fn_name}")

        routes = apigw.get_routes(ApiId=api_id).get("Items", [])
        route_key = f"{method} {path}"
        route_id = None
        for route in routes:
            if route.get("RouteKey") == route_key:
                route_id = route["RouteId"]
                break
        if not route_id:
            apigw.create_route(
                ApiId=api_id,
                RouteKey=route_key,
                Target=f"integrations/{integration_id}",
            )
            print(f"Created route {route_key}")
        else:
            apigw.update_route(
                ApiId=api_id,
                RouteId=route_id,
                Target=f"integrations/{integration_id}",
            )
            print(f"Updated route {route_key}")

        statement_id = f"apigw-{api_id}-{fn_name}".replace("_", "")[:100]
        source_arn = f"arn:aws:execute-api:{reg}:{account}:{api_id}/*/*{path}"
        _add_permission(
            lam,
            function_name=fn_name,
            statement_id=statement_id,
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=source_arn,
        )

    return f"https://{api_id}.execute-api.{reg}.amazonaws.com/prod"


def write_endpoints(payload: dict) -> Path:
    out = ROOT / "build" / "api_endpoints.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {out}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy BookingApp Lambda APIs")
    parser.add_argument(
        "--only",
        help="Comma-separated function names to update (default: all)",
        default="",
    )
    args = parser.parse_args()
    only = {n.strip() for n in args.only.split(",") if n.strip()}

    reg = region()
    session = boto3.Session(region_name=reg)
    sts = session.client("sts")
    iam = session.client("iam")
    lam = session.client("lambda")
    apigw = session.client("apigatewayv2")
    account = account_id(sts)
    print(f"Account={account} Region={reg}", flush=True)

    zip_path = package_zip()
    role_arn = ensure_role(iam, account, reg)

    all_fns = {**FUNCTIONS, **CONNECT_FUNCTIONS}
    selected = (
        {k: v for k, v in all_fns.items() if k in only} if only else all_fns
    )
    if only and not selected:
        print(f"ERROR: no matching functions for --only {args.only}", file=sys.stderr)
        return 1

    print(f"Deploying {len(selected)} function(s)…", flush=True)
    for fn_name, meta in selected.items():
        ensure_function(lam, fn_name, meta["handler"], role_arn, zip_path, reg)

    # Function URLs / HTTP API only for public API functions that were selected
    # (or all, when deploying everything).
    public = {k: v for k, v in FUNCTIONS.items() if k in selected}
    function_urls: dict[str, str] = {}
    if public:
        # ensure_function_urls iterates FUNCTIONS; temporarily filter via copy path
        original = dict(FUNCTIONS)
        FUNCTIONS.clear()
        FUNCTIONS.update(public)
        try:
            function_urls = ensure_function_urls(lam)
        finally:
            FUNCTIONS.clear()
            FUNCTIONS.update(original)

    api_base = None
    if public:
        try:
            original = dict(FUNCTIONS)
            FUNCTIONS.clear()
            FUNCTIONS.update(public)
            try:
                api_base = ensure_http_api(apigw, lam, account, reg)
            finally:
                FUNCTIONS.clear()
                FUNCTIONS.update(original)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
                print(
                    "API Gateway 権限なし → Lambda Function URL で公開します。",
                    file=sys.stderr,
                )
            else:
                raise

    print("OK", flush=True)
    if api_base:
        print(f"API Gateway Base URL: {api_base}")
        print(f"  POST {api_base}/auth/login")
        print(f"  POST {api_base}/auth/logout")
        print(f"  POST {api_base}/auth/me")
        print(f"  POST {api_base}/applications/create")
        print(f"  POST {api_base}/applications/list")
        print(f"  POST {api_base}/applications/review")
        print(f"  POST {api_base}/availability/check")
        print(f"  POST {api_base}/reservations/confirm")
        print(f"  POST {api_base}/reservations/list")
        print(f"  POST {api_base}/store/get")
        print(f"  POST {api_base}/store/update")
        write_endpoints(
            {
                "mode": "api_gateway",
                "baseUrl": api_base,
                "login": f"{api_base}/auth/login",
                "logout": f"{api_base}/auth/logout",
                "authMe": f"{api_base}/auth/me",
                "createApplication": f"{api_base}/applications/create",
                "listApplications": f"{api_base}/applications/list",
                "reviewApplication": f"{api_base}/applications/review",
                "checkAvailability": f"{api_base}/availability/check",
                "confirmReservation": f"{api_base}/reservations/confirm",
                "listReservations": f"{api_base}/reservations/list",
                "getStore": f"{api_base}/store/get",
                "updateStore": f"{api_base}/store/update",
                "functionUrls": function_urls,
            }
        )
    elif function_urls:
        print("Function URLs:")
        for key, url in function_urls.items():
            print(f"  {key}: {url}")
        write_endpoints({"mode": "function_url", **function_urls})

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        msg = exc.response["Error"]["Message"]
        print(f"ERROR [{code}]: {msg}", file=sys.stderr)
        if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
            print(
                "IAMユーザー cursor に Lambda / IAM Role 作成権限を追加してください。"
                " API Gateway が無くても Function URL で公開できます。"
                " 詳細は infra/cursor_deployer_policy.json / infra/README.md。",
                file=sys.stderr,
            )
        raise SystemExit(1)

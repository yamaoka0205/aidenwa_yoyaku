# Infrastructure

## BookingApp（DynamoDB）

`DB設計.md` に従った単一テーブル。

| 項目 | 値 |
|---|---|
| テーブル名 | `BookingApp` |
| PK / SK | `PK` (S) / `SK` (S) |
| 課金 | オンデマンド（`PAY_PER_REQUEST`） |
| GSI | `GSI1`（`GSI1PK` / `GSI1SK`、Projection ALL） |
| TTL | `expiresAt` |

GSI2 は完成系（申し込み一覧など）で有効化する。属性名は設計書どおり空けておく。

## ローカルで作る

```bash
# 別ターミナルで DynamoDB Local を起動
./scripts/start_dynamodb_local.sh

# テーブル作成（冪等）
python3 scripts/create_table.py --endpoint-url http://localhost:8000
```

## AWS で作る

前提: 環境に `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_DEFAULT_REGION` が入っていること（値はリポジトリに書かない）。

```bash
# boto3 + 認証情報がある場合
python3 scripts/create_table.py --region ap-northeast-1

# または CloudFormation
aws cloudformation deploy \
  --template-file infra/booking_app_table.yaml \
  --stack-name booking-app-table \
  --region ap-northeast-1
```

東京リージョンに `BookingApp` を作成済み（IAM ユーザー `cursor`）。再実行は冪等で、既存テーブルはそのまま使う。

## デモ店のシード

```bash
python3 scripts/seed_demo_store.py

# 転送先番号を入れる場合（リポジトリには書かない）
TRANSFER_PHONE_NUMBER=+81... python3 scripts/seed_demo_store.py
```

投入内容（`t_demo_001` / 着信先 `+810000000001`）。既存の店の着信先が違えば、1トランザクションで張り替える：

- `PROFILE` + `INBOUND#`
- `HOURS#`（月〜土 11:00-22:00、日定休、最終開始 20:00）
- `TABLE#`（AI予約: 4人用4卓 + 6人用2卓、当日客用: 4人用2卓）

## 空席確認API（ローカルから Lambda ハンドラを直叩き）

```bash
PYTHONPATH=src python3 scripts/invoke_check_availability.py \
  --tenant-id t_demo_001 --date 2026-11-16 --start-time 19:00 --party-size 4
```

返却例: `available` / `full` / `closed` / `outside_hours` / `invalid_slot` / `human_handoff`

## 予約確定API

```bash
PYTHONPATH=src python3 scripts/invoke_confirm_reservation.py \
  --tenant-id t_demo_001 --date 2026-11-18 --start-time 19:00 --party-size 4 \
  --customer-name '山田太郎'
```

成功時は `RES#` と占有 `SLOT#` を `TransactWriteItems` で同時作成する。衝突時は別卓を試し、なければ `full`（HTTP 409）。

## Lambda へ公開（Function URL / API Gateway）

`scripts/deploy_api.py` は Lambda 2 本を上げ、**Lambda Function URL** で HTTPS 公開する。  
API Gateway 権限があれば HTTP API も作る（無くても Function URL だけで動く）。

### 1. IAM（コンソール・管理者）

IAM → ユーザー `cursor` → 許可を追加。

最低限（Function URL 公開）:

- `AWSLambda_FullAccess`
- 実行ロール作成用: `IAMFullAccess`（仮）または `infra/cursor_deployer_policy.json`

任意（共通パスの API Gateway）:

- `AmazonAPIGatewayAdministrator`

### 2. デプロイ

```bash
python3 scripts/deploy_api.py
# → build/api_endpoints.json に URL が書かれる
```

```bash
CHECK=$(python3 -c 'import json;print(json.load(open("build/api_endpoints.json"))["checkAvailability"])')
curl -sS -X POST "$CHECK" \
  -H 'content-type: application/json' \
  -d '{"tenantId":"t_demo_001","date":"2026-11-16","startTime":"19:00","partySize":4}'
```

実AWSでは API Gateway HTTP API（`yme1o14ql5`）と Function URL の両方で 空席確認・予約確定を確認済み。ベースURLは `build/api_endpoints.json` を参照。

管理画面用（Phase 3）:

- `POST .../auth/login` … Cognito ログイン
- `POST .../auth/logout` … Cognito ログアウト
- `POST .../auth/me` … セッション確認
- `POST .../reservations/list` … 日付の予約一覧（要ログイン）
- `POST .../store/get` … 店舗設定取得（要ログイン）
- `POST .../store/update` … 店舗設定更新（要ログイン）

認証セットアップ:

```bash
python3 scripts/setup_cognito_admin.py
python3 scripts/seed_demo_admin.py
python3 scripts/deploy_api.py
```

フロントは `admin/`（`npm run dev`）。

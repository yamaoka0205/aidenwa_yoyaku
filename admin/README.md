# 管理画面（Phase 3）

紙・Excel管理から初めて移る店舗向けに、**予約一覧と手動予約・最小設定**だけに絞った画面です。

## 方針（使いやすさ最優先）

- ログイン／ログアウトあり（Amazon Cognito）
- 正面は「今日の予約」一覧（時刻が大きい・人数が丸・名前が太い）
- 予約登録は右シート。人数・時刻は大きなチップ
- 確定後は緑の完了表示（入力画面と区別）
- 設定は「基本 → 営業時間 → 席の確認 → FAQ」の4ブロック
- ナビはアイコン＋ラベル（アイコンだけにしない）

## デモ用ログイン（Cognito）

```
メール: demo@sakura.local
パスワード: Demo-pass-2026!
```

```bash
python3 scripts/setup_cognito_admin.py   # User Pool / デモユーザー
python3 scripts/seed_demo_admin.py       # MEMBERSHIP（店舗紐づけ）
python3 scripts/deploy_api.py            # Lambda に Cognito 設定を渡す
```

## 起動

```bash
cd admin
cp .env.example .env.local
# .env.local の VITE_API_BASE_URL に API Gateway の base URL を入れる
# （scripts/deploy_api.py 実行後の build/api_endpoints.json の baseUrl）
npm install
npm run dev
```

ブラウザで `http://localhost:5173` を開く。  
開発時は `/api/*` を Vite が `VITE_API_BASE_URL` へプロキシします。

## 必要な API

| 経路 | 用途 |
|---|---|
| `POST /auth/login` | ログイン |
| `POST /auth/logout` | ログアウト |
| `POST /auth/me` | セッション確認 |
| `POST /reservations/list` | 日付の予約一覧（要ログイン） |
| `POST /reservations/confirm` | 手動予約（要ログイン） |
| `POST /availability/check` | 空席確認（要ログイン） |
| `POST /store/get` | 店舗設定取得（要ログイン） |
| `POST /store/update` | 店舗設定更新（要ログイン） |

デプロイ: リポジトリルートで `python3 scripts/deploy_api.py`

# Amazon Connect（BookingApp）

## フロー名

**`BookingApp-Inbound`**（全店共通・CONTACT_FLOW）

| 項目 | 値 |
|---|---|
| 名前 | `BookingApp-Inbound` |
| ContactFlowId | `e777dddc-a817-425b-b579-6f515a3f07d8` |
| インスタンス | `syusyoku-connect`（`98c809c0-0dd7-414f-979a-bf7816f5bfae`） |
| Lex ボット | `BookingAppPhone`（locale `ja_JP`、alias `live`） |

## 動き

1. 日本語音声（Mizuki）
2. `BookingAppResolveStore` で店舗特定（普通の電話／非通知／WebRTC）
3. 「〇〇店です。ご予約は1、それ以外は2」
4. **1** → Lex（ASR/TTS）+ Lambda `BookingAppPhoneTurn`（人数→日時→名前→空席→復唱→確定）。判定はサンプル発話ではなく Lambda / Bedrock
5. **2** → Lex + Lambda FAQ（Bedrock）
6. 入力なし・1/2以外は1回だけやり直し

Lex の短い返答（「4」など）は NLU 上 FallbackIntent になりやすい。`FallbackIntent` にも同じ Lambda を繋ぎ、`intentHint` で予約/FAQに戻す。

## 通信ウィジェットへの紐づけ（コンソール・要作業）

1. Connect 管理画面 → **チャネル** → **通信ウィジェット**
2. 使っている音声ウィジェットを開く
3. 着信時のフローを **`BookingApp-Inbound`** に変更して保存
4. 許可ドメインに `http://localhost:3000` が入っていることを確認

紐づけ後、`http://localhost:3000` から発信して店名と 1/2 を確認する。

## デプロイ

```bash
python3 scripts/deploy_api.py          # Lambda（Resolve / Reservation / FAQ / PhoneTurn）
python3 scripts/deploy_lex_bot.py      # Lex V2 ボット
python3 scripts/deploy_connect_flow.py # Connect フロー更新
python3 scripts/seed_demo_store.py     # FAQ 込みシード
```

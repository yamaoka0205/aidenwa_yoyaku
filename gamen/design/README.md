# よやく台帳 UIデザイン（Claude 成果物）

`design-handoff.md` を元に Claude が出力したデザイン一式です。

## 開き方

1. **バンドル版（推奨）**  
   `よやく台帳_UIデザイン.html` をブラウザで開く（画面切替つき）。JS必須。
2. **単体画面**  
   `screens-unpacked/*.html` を直接開く（インラインスタイルの静的HTML）。

## 画面一覧

| # | ファイル | 内容 |
|---|---|---|
| 01 | `screens-unpacked/01-ledger-timeline.html` | 台帳タイムライン版（R1・iPad横想定） |
| 02 | `screens-unpacked/02-ledger-list.html` | 台帳リスト版（MVP） |
| 03 | `screens-unpacked/03-ledger-empty.html` | 台帳・空状態 |
| 04 | `screens-unpacked/04-reservation-sheet.html` | 新規予約シート |
| 05 | `screens-unpacked/05-settings.html` | お店の設定 |
| 06 | `screens-unpacked/06-store-login.html` | 店舗ログイン |
| 07 | `screens-unpacked/07-apply.html` | 店舗申し込み |
| 08 | `screens-unpacked/08-lp.html` | 紹介LP |
| 09 | `screens-unpacked/09-operator.html` | 運営・申し込み承認 |
| 10 | `screens-unpacked/10-tokens.html` | トークン・コンポーネント |

`screens/` は入れ子バンドルのままの抽出物。閲覧は `screens-unpacked/` を使う。

## デザインの要点（実装への引き継ぎ）

- 色: 台帳 `#F7F7F5` / `#1C1917` / `#2563EB` / `#16A34A` / `#E11D48`。LP ヘッダー `#0F766E`、CTA `#F97316`
- フォント: Noto Sans JP、数字は `tabular-nums`
- タップ最小 44px、チップ・主ボタンは大きめ
- LPヒーローの主ビジュアルは**タイムライン台帳の製品UI**（店内写真なし）
- 料金表示: 基本 3,000円／月 ＋ 通話 50円／分（税別）、初期費用 0円

## 関連

- 依頼ブリーフ: `../doc/design-handoff.md`
- UX仕様・R1: `../doc/restaurant-ledger-ux-review.md`
- 実装: `../../admin/`

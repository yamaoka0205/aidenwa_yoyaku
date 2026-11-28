# 参照: AIHelpdesk Connect フロー

`AIHelpdeskFlow.json` は別プロジェクトの Connect フロー書き出し。

BookingApp-Inbound は同じ型で組んでいる:

1. Lookup / Resolve（Lambda）
2. Connect が質問を再生
3. Lex（Text 空白）で文字起こし → Lambda が `sessionAttributes` に結果
4. Connect が `aiResponseText` を再生し `routingAction` で分岐

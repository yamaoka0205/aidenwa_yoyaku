"""Pull reservation fields out of a Japanese utterance.

Uses Bedrock when BEDROCK_MODEL_ID is set and InvokeModel is allowed.
Otherwise falls back to deterministic regex/heuristics so dialogs can be
developed and tested without Bedrock IAM.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from booking.timeutil import local_now

WEEKDAY_JA = {
    "月": 0,
    "火": 1,
    "水": 2,
    "木": 3,
    "金": 4,
    "土": 5,
    "日": 6,
}
KANJI_NUM = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


@dataclass
class ExtractedSlots:
    date: str | None = None
    time: str | None = None
    party_size: int | None = None
    name: str | None = None
    intent: str | None = None  # reserve | faq | unknown
    source: str = "rules"


def _parse_relative_date(text: str, today: date) -> str | None:
    if "明後日" in text:
        return (today + timedelta(days=2)).isoformat()
    if "明日" in text:
        return (today + timedelta(days=1)).isoformat()
    if "今日" in text:
        return today.isoformat()

    m = re.search(r"(今週|来週)?の?([月火水木金土日])曜", text)
    if m:
        weeks = 1 if m.group(1) == "来週" else 0
        wd = WEEKDAY_JA[m.group(2)]
        days = (wd - today.weekday()) % 7
        if weeks == 0 and days == 0:
            target = today
        elif weeks == 0:
            target = today + timedelta(days=days)
        else:
            # next week's that weekday (if today is that day, still next week)
            if days == 0:
                target = today + timedelta(days=7)
            else:
                target = today + timedelta(days=days + 7)
        return target.isoformat()

    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = today.year
        try:
            candidate = date(year, month, day)
        except ValueError:
            return None
        if candidate < today:
            candidate = date(year + 1, month, day)
        return candidate.isoformat()
    return None


def _parse_time(text: str) -> str | None:
    m = re.search(r"(\d{1,2})\s*[:：]\s*(\d{2})", text)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"

    m = re.search(r"(\d{1,2})\s*時\s*(半|(\d{1,2})\s*分)?", text)
    if m:
        hour = int(m.group(1))
        if m.group(2) == "半":
            minute = 30
        elif m.group(3):
            minute = int(m.group(3))
        else:
            minute = 0
        if "夜" in text and hour < 12:
            hour += 12
        if "午後" in text and hour < 12:
            hour += 12
        if hour == 24:
            hour = 0
        return f"{hour:02d}:{minute:02d}"
    return None


_SPOKEN_PARTY = {
    "ひとり": 1,
    "一人": 1,
    "いち": 1,
    "ひとつ": 1,
    "ふたり": 2,
    "二人": 2,
    "に": 2,
    "ににん": 2,
    "さんにん": 3,
    "三人": 3,
    "さん": 3,
    "よにん": 4,
    "四人": 4,
    "よん": 4,
    "し": 4,
    "ごにん": 5,
    "五人": 5,
    "ご": 5,
    "ろくにん": 6,
    "六人": 6,
    "ろく": 6,
    "ななにん": 7,
    "七人": 7,
    "なな": 7,
}


def _parse_party(text: str) -> int | None:
    t = (text or "").strip()
    # Lex ASR often returns bare "4" / "４" for party size turns.
    m = re.fullmatch(r"[0-9０-９]{1,2}", t)
    if m:
        n = int(t.translate(str.maketrans("０１２３４５６７８９", "0123456789")))
        return n
    m = re.search(r"(\d{1,2})\s*名", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{1,2})\s*人", t)
    if m:
        return int(m.group(1))
    m = re.search(r"([一二三四五六七八九十])\s*人", t)
    if m:
        return KANJI_NUM.get(m.group(1))
    compact = re.sub(r"[\s　]", "", t)
    if compact in _SPOKEN_PARTY:
        return _SPOKEN_PARTY[compact]
    return None


def _parse_name(text: str) -> str | None:
    m = re.search(r"([ァ-ヶー]{2,20})(?:です|と申します|でお願いします)?", text)
    if m:
        return m.group(1)
    m = re.search(r"名前[はが]?\s*([一-龥ぁ-んァ-ヶー]{1,20})", text)
    if m:
        return m.group(1)
    return None


def _guess_intent(text: str) -> str:
    if any(k in text for k in ("予約", "取りたい", "空いて", "席")):
        return "reserve"
    if any(k in text for k in ("営業", "何時", "住所", "駐車場", "禁煙", "個室", "聞きたい")):
        return "faq"
    return "unknown"


def extract_with_rules(text: str, *, tz_name: str = "Asia/Tokyo") -> ExtractedSlots:
    today = local_now(tz_name).date()
    return ExtractedSlots(
        date=_parse_relative_date(text, today),
        time=_parse_time(text),
        party_size=_parse_party(text),
        name=_parse_name(text),
        intent=_guess_intent(text),
        source="rules",
    )


def _bedrock_model_id() -> str:
    return os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")


def extract_with_bedrock(
    text: str, *, known: dict[str, Any] | None = None, tz_name: str = "Asia/Tokyo"
) -> ExtractedSlots | None:
    model_id = _bedrock_model_id()
    try:
        import boto3
    except ImportError:
        return None

    today = local_now(tz_name).date()
    prompt = {
        "today": today.isoformat(),
        "weekday": today.strftime("%A"),
        "known": known or {},
        "utterance": text,
        "instruction": (
            "Extract reservation fields from the Japanese utterance. "
            "Return JSON only with keys date (yyyy-mm-dd), time (HH:MM), "
            "partySize (int), name (string), intent (reserve|faq|unknown). "
            "Use null for unknown fields. Do not invent facts."
        ),
    }
    body = {
        "messages": [
            {
                "role": "user",
                "content": [{"text": json.dumps(prompt, ensure_ascii=False)}],
            }
        ],
        "inferenceConfig": {"maxTokens": 300, "temperature": 0},
    }
    try:
        client = boto3.client("bedrock-runtime")
        resp = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body).encode("utf-8"),
        )
        payload = json.loads(resp["body"].read())
        # Nova / Converse-like shapes
        raw = ""
        if "output" in payload and "message" in payload["output"]:
            parts = payload["output"]["message"].get("content") or []
            raw = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        elif "content" in payload:
            raw = "".join(
                p.get("text", "") for p in payload["content"] if isinstance(p, dict)
            )
        else:
            raw = json.dumps(payload)
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return None
        data = json.loads(m.group(0))
        party = data.get("partySize")
        return ExtractedSlots(
            date=data.get("date"),
            time=data.get("time"),
            party_size=int(party) if party is not None else None,
            name=data.get("name"),
            intent=data.get("intent") or "unknown",
            source="bedrock",
        )
    except Exception:  # noqa: BLE001
        return None


def extract_slots(
    text: str, *, known: dict[str, Any] | None = None, tz_name: str = "Asia/Tokyo"
) -> ExtractedSlots:
    bedrock = extract_with_bedrock(text, known=known, tz_name=tz_name)
    rules = extract_with_rules(text, tz_name=tz_name)
    if not bedrock:
        return rules
    # Prefer Bedrock values when present; fill gaps from rules.
    return ExtractedSlots(
        date=bedrock.date or rules.date,
        time=bedrock.time or rules.time,
        party_size=bedrock.party_size if bedrock.party_size is not None else rules.party_size,
        name=bedrock.name or rules.name,
        intent=bedrock.intent if bedrock.intent != "unknown" else rules.intent,
        source="bedrock",
    )


def slots_to_dict(slots: ExtractedSlots) -> dict[str, Any]:
    return asdict(slots)

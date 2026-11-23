#!/usr/bin/env python3
"""Invoke list_reservations handler locally."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from handlers.list_reservations import handler  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tenant-id", default="t_demo_001")
    p.add_argument("--date", required=True)
    args = p.parse_args()
    result = handler({"tenantId": args.tenant_id, "date": args.date})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

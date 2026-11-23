#!/usr/bin/env python3
"""Invoke get_store handler locally."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from handlers.get_store import handler  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tenant-id", default="t_demo_001")
    args = p.parse_args()
    result = handler({"tenantId": args.tenant_id})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_json.py — 2025 最終穩定版
產生：
- data/games_full.json（完整）
- site/data/games.json（前端使用）
"""

import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "bgg_data.json"
OUT_FULL = ROOT / "data" / "games_full.json"
OUT_SITE = ROOT / "site" / "data" / "games.json"

SRC.parent.mkdir(exist_ok=True)
OUT_SITE.parent.mkdir(parents=True, exist_ok=True)

data = json.loads(SRC.read_text("utf-8")) if SRC.exists() else []

# FULL（美化）
OUT_FULL.write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    "utf-8"
)

# SITE（壓縮 → 單行）
OUT_SITE.write_text(
    json.dumps(data, ensure_ascii=False),
    "utf-8"
)

print("[OK] build_json.py 完成")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish_games.py

目的：
- 確保 site/data/games.json 一定是 `list[dict]` 結構，給前端直接使用。
- 不再改動欄位，只做「來源選擇＋結構修正」。
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULL = ROOT / "data" / "games_full.json"
RAW  = ROOT / "data" / "bgg_data.json"
OUT  = ROOT / "site" / "data" / "games.json"


def load_source():
    """優先使用 games_full.json，沒有就退回 bgg_data.json。"""
    src = FULL if FULL.exists() else RAW
    if not src.exists():
        raise SystemExit("publish_games: no input JSON (games_full.json / bgg_data.json 都不存在)")
    text = src.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except Exception as e:
        raise SystemExit(f"publish_games: JSON parse error in {src}: {e}")
    return src, data


def normalize_rows(data):
    """
    將 data 統一變成 list[dict]：
    - 若是 list：直接回傳（濾掉非 dict）
    - 若是 dict 且有 key 'rows' 是 list：取 rows
    - 其他情況：視為錯誤
    """
    if isinstance(data, list):
        rows = [r for r in data if isinstance(r, dict)]
        return rows

    if isinstance(data, dict):
        maybe_rows = data.get("rows")
        if isinstance(maybe_rows, list):
            rows = [r for r in maybe_rows if isinstance(r, dict)]
            return rows
        # 若你真的想支援其他結構，可以再補，但目前先明確 fail，避免靜靜寫出壞檔案
        raise SystemExit("publish_games: input dict has no 'rows' list; please inspect upstream script")

    raise SystemExit("publish_games: input JSON is neither list nor dict")


def main():
    src, data = load_source()
    rows = normalize_rows(data)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"publish_games: mode=games_full ; rows={len(rows)} → {OUT} (from {src})")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish_games.py

目的：
- 統一資料來源：以前這支腳本會直接從 bgg_data.json 重算欄位與圖片，
  容易跟 build_json.py 打架，導致前面修正被覆蓋。
- 現在改成「只做 passthrough」：
  - 讀取 data/games_full.json
  - 寫出 site/data/games.json
  如此 build_json.py 就是唯一的真實來源。
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
FULL = ROOT / "data" / "games_full.json"
FALLBACK = ROOT / "data" / "bgg_data.json"
OUT = ROOT / "site" / "data" / "games.json"

def main() -> int:
    if FULL.exists():
        src = FULL
        rows = json.loads(FULL.read_text(encoding="utf-8"))
        mode = "games_full"
    else:
        # 極端狀況：若 build_json 還沒跑成功，就退回用 bgg_data.json 原始資料
        if not FALLBACK.exists():
            print("[publish_games] ERROR: 找不到 games_full.json 或 bgg_data.json，無法發布。")
            return 1
        src = FALLBACK
        rows = json.loads(FALLBACK.read_text(encoding="utf-8"))
        mode = "bgg_data (fallback)"

    if not isinstance(rows, list):
        print(f"[publish_games] ERROR: {src} 內容不是 list")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    print(f"publish_games: mode={mode} ; rows={len(rows)} → {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

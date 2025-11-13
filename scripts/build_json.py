#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
產出兩份：
1) data/games_full.json（完整清單，供檢查）
2) site/data/games.json（網站實際讀取）
並做舊鍵名相容與欄位補齊（players、time、rating_avg 等）
"""

import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_IN  = ROOT / "data" / "bgg_data.json"
OUT_FULL = ROOT / "data" / "games_full.json"
OUT_SITE = ROOT / "site" / "data" / "games.json"

def _compat(r: dict) -> dict:
    r = dict(r)

    # ---- 舊→新鍵名相容 ----
    r.setdefault("min_players", r.get("minplayers"))
    r.setdefault("max_players", r.get("maxplayers"))
    r.setdefault("min_playtime", r.get("minplaytime"))
    r.setdefault("max_playtime", r.get("maxplaytime"))
    r.setdefault("rating_avg",  r.get("rating"))         # 供前端 getRatingAvg()
    # rating_bayes 若抓到就保留；沒有就不補

    # players 陣列供前端徽章
    mn_p = r.get("minplayers") or r.get("min_players")
    mx_p = r.get("maxplayers") or r.get("max_players")
    if mn_p or mx_p:
        r["players"] = [mn_p or mx_p, mx_p or mn_p]

    # BGG URL
    bid = r.get("bgg_id") or r.get("id")
    if bid:
        r.setdefault("bgg_url", f"https://boardgamegeek.com/boardgame/{int(bid)}")

    # 影像相容
    if not r.get("image_url"):
        r["image_url"] = (r.get("image") or r.get("thumbnail") or r.get("thumb_url") or "")
    if not r.get("thumb_url"):
        r["thumb_url"] = (r.get("thumbnail") or r.get("image") or r.get("image_url") or "")

    # 類別／機制：保留 BGG 原文
    r.setdefault("categories", r.get("categories", []) or [])
    r.setdefault("mechanics",  r.get("mechanisms", []) or r.get("mechanics", []) or [])
    return r

def main():
    if not DATA_IN.exists():
        print("bgg_data.json not found", file=sys.stderr)
        sys.exit(0)

    rows = json.loads(DATA_IN.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        rows = []

    rows = [_compat(x) for x in rows]

    # 寫出
    OUT_FULL.parent.mkdir(parents=True, exist_ok=True)
    OUT_SITE.parent.mkdir(parents=True, exist_ok=True)

    OUT_FULL.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_SITE.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")

    print(f"games_full.json rows={len(rows)} ; wrote → {OUT_FULL}")
    print(f"site/data/games.json rows={len(rows)} ; wrote → {OUT_SITE}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
normalize_bgg_data.py — 2025 最終穩定版
欄位相容處理 + 清洗資料 + 合併分類 / 機制
"""

import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
F = ROOT / "data" / "bgg_data.json"

if not F.exists():
    print("bgg_data.json 不存在")
    exit(0)

data = json.loads(F.read_text("utf-8"))
out = []

for g in data:
    g2 = dict(g)

    # 欄位相容：舊名 → 新名
    if "minplayers" in g2:
        g2["min_players"] = g2.get("minplayers")
    if "maxplayers" in g2:
        g2["max_players"] = g2.get("maxplayers")
    if "minplaytime" in g2:
        g2["min_playtime"] = g2.get("minplaytime")
    if "maxplaytime" in g2:
        g2["max_playtime"] = g2.get("maxplaytime")

    # 合併分類
    cats = set(g2.get("categories", []))
    if g2.get("category_zh"):
        cats.add(g2["category_zh"])

    # 合併機制
    mechs = set(g2.get("mechanisms", []))

    g2["categories"] = sorted(list(cats))
    g2["mechanisms"] = sorted(list(mechs))

    out.append(g2)

F.write_text(json.dumps(out, ensure_ascii=False, indent=2), "utf-8")

print("[OK] normalize_bgg_data.py 完成")

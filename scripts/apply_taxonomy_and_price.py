#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_taxonomy_and_price.py — 2025 最終穩定版
合併 override.json → bgg_data.json
補上價格 / 庫存 / 中文類別 / 搜尋關鍵字
"""

import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
BGG_FILE = ROOT / "data" / "bgg_data.json"
OVERRIDE_FILE = ROOT / "data" / "override.json"

# ------------------------------------------------------
# 載入 BGG 資料
# ------------------------------------------------------
if BGG_FILE.exists():
    base_list = json.loads(BGG_FILE.read_text("utf-8"))
    base = {g["bgg_id"]: g for g in base_list}
else:
    base = {}

# ------------------------------------------------------
# 載入 override（價格 / 庫存 / 中文分類）
# ------------------------------------------------------
if OVERRIDE_FILE.exists():
    overrides = json.loads(OVERRIDE_FILE.read_text("utf-8"))
else:
    overrides = []

for row in overrides:
    gid = row.get("bgg_id")
    if gid not in base:
        continue

    g = base[gid]

    for k in [
        "name_zh", "price_msrp_twd", "price_twd", "used_price_twd",
        "manual_override", "stock", "category_zh", "alias_zh",
        "image_override", "bgg_url_override"
    ]:
        if row.get(k) not in [None, "", []]:
            g[k] = row[k]

# ------------------------------------------------------
# 建立搜尋關鍵字
# ------------------------------------------------------
for g in base.values():
    keys = []
    for k in ["name", "name_zh", "alias_zh"]:
        if g.get(k):
            keys.append(g[k])

    keys.extend(g.get("categories", []))
    keys.extend(g.get("mechanisms", []))

    if g.get("category_zh"):
        keys.append(g["category_zh"])

    g["search_keywords"] = keys

# ------------------------------------------------------
# 寫回去
# ------------------------------------------------------
BGG_FILE.write_text(
    json.dumps(list(base.values()), ensure_ascii=False, indent=2),
    "utf-8"
)

print("[OK] apply_taxonomy_and_price.py 完成")


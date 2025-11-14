#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_json.py — 2025 穩定完整版本
目的：
1) 產出 data/games_full.json（完整美化）
2) 產出 site/data/games.json（網站使用，含欄位補齊＋相容）

網站規格支援：
- 必備欄位：rating_bayes / rating_avg / users_rated / weight / mechanism_count
- image pipeline：優先 image_override，否則 assets/img/{bgg_id}-{hash}.jpg
- 相容欄位：minplayers → min_players 等
"""

import json
import hashlib
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "bgg_data.json"
OUT_FULL = ROOT / "data" / "games_full.json"
OUT_SITE = ROOT / "site" / "data" / "games.json"

SRC.parent.mkdir(exist_ok=True)
OUT_SITE.parent.mkdir(parents=True, exist_ok=True)

data = json.loads(SRC.read_text("utf-8")) if SRC.exists() else []


def _compat(r: dict) -> dict:
    """欄位補齊＋舊鍵名相容"""
    r = dict(r)

    # 玩家數
    r.setdefault("min_players", r.get("minplayers"))
    r.setdefault("max_players", r.get("maxplayers"))

    # 遊玩時間
    r.setdefault("min_playtime", r.get("minplaytime"))
    r.setdefault("max_playtime", r.get("maxplaytime"))

    # 評分
    r.setdefault("rating", r.get("rating_avg"))
    r.setdefault("rating_avg", r.get("rating"))
    r.setdefault("rating_bayes", r.get("bayesaverage"))
    r.setdefault("users_rated", r.get("usersrated"))

    # 重量（兩種欄位相容）
    r.setdefault("weight", r.get("weight_avg"))
    r.setdefault("weight_avg", r.get("weight"))

    # 機制數
    if "mechanisms" in r and isinstance(r["mechanisms"], list):
        r["mechanism_count"] = len(r["mechanisms"])
    else:
        r["mechanism_count"] = 0

    return r


def _image_for(r: dict) -> str | None:
    """決定圖片路徑（網站規格 v2025）"""

    # 1) image_override → 完全尊重
    if r.get("image_override"):
        return f"assets/img/{r['image_override']}"

    # 2) BGG 原圖 → 用哈希生成本地檔名（你既有的 pipeline）
    if r.get("image"):
        ext = pathlib.Path(r["image"]).suffix or ".jpg"
        h = hashlib.md5(r["image"].encode("utf-8")).hexdigest()[:8]
        return f"assets/img/{r['bgg_id']}-{h}{ext}"

    return None


# === Main process ===
out_rows = []

for row in data:
    r = _compat(row)
    r["image"] = _image_for(r)
    out_rows.append(r)

# FULL（美化）
OUT_FULL.write_text(
    json.dumps(out_rows, ensure_ascii=False, indent=2),
    "utf-8"
)

# SITE（壓縮）
OUT_SITE.write_text(
    json.dumps(out_rows, ensure_ascii=False),
    "utf-8"
)

print(f"[OK] build_json.py 完成；rows={len(out_rows)}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
從 data/bgg_data.json 產生：

1) data/games_full.json  ─ 完整欄位，方便檢查
2) site/data/games.json   ─ 網站實際讀取用（欄位同上，只是壓縮格式）

會輸出的重點欄位（前端現在都會吃）：
- id, name, year
- minplayers, maxplayers, minplaytime, maxplaytime
- rating, rating_avg, rating_bayes, usersrated, users_rated
- weight, weight_avg, mechanism_count
- image, thumbnail, image_override, image_version_id
- categories, mechanisms
- bgg_id, bgg_url, source
- name_zh, name_en, alias_zh, description
- price_msrp_twd, price_twd, used_price_twd, price_note, used_note
- manual_override, stock
"""

from __future__ import annotations
import json
import pathlib
from typing import Any, Dict

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SITE_DATA_DIR = ROOT / "site" / "data"

BGG_JSON = DATA_DIR / "bgg_data.json"
OUT_FULL = DATA_DIR / "games_full.json"
OUT_SITE = SITE_DATA_DIR / "games.json"


def _make_id(rec: Dict[str, Any]) -> str:
    """以名稱 + bgg_id 產生穩定 id。"""
    bgg_id = str(rec.get("bgg_id") or "").strip()
    base = (rec.get("name") or rec.get("name_en") or rec.get("name_zh") or "").strip()
    slug = base.replace(" ", "_").replace("/", "-")
    if bgg_id:
        return f"{slug}-{bgg_id}" if slug else bgg_id
    return slug or bgg_id or "unknown"


def _compat(rec: Dict[str, Any]) -> Dict[str, Any]:
    """統一欄位名稱＋補齊需要的欄位。"""
    r = dict(rec)

    # 舊欄位名稱兼容
    r.setdefault("min_players", r.get("minplayers"))
    r.setdefault("max_players", r.get("maxplayers"))
    r.setdefault("min_playtime", r.get("minplaytime"))
    r.setdefault("max_playtime", r.get("maxplaytime"))
    r.setdefault("users_rated", r.get("usersrated"))
    r.setdefault("weight", r.get("weight_avg"))

    categories = r.get("categories") or []
    mechanisms = r.get("mechanisms") or r.get("mechanics") or []

    # 基本欄位
    out: Dict[str, Any] = {
        "id": _make_id(r),
        "name": r.get("name") or r.get("name_en") or r.get("name_zh") or "",
        "year": r.get("year"),
        "minplayers": r.get("min_players"),
        "maxplayers": r.get("max_players"),
        "minplaytime": r.get("min_playtime"),
        "maxplaytime": r.get("max_playtime"),
        "weight": r.get("weight"),
        "weight_avg": r.get("weight"),
        "rating_avg": r.get("rating_avg") or r.get("rating"),
        "rating": r.get("rating_avg") or r.get("rating"),
        "rating_bayes": r.get("rating_bayes"),
        "users_rated": r.get("users_rated"),
        "usersrated": r.get("users_rated"),
        "image": r.get("image"),
        "thumbnail": r.get("thumbnail"),
        "categories": categories,
        "mechanisms": mechanisms,
        "mechanism_count": r.get("mechanism_count") or len(mechanisms),
        "source": r.get("source") or "bgg",
        "bgg_id": r.get("bgg_id"),
    }

    # BGG 連結
    bgg_id = r.get("bgg_id")
    bgg_url = r.get("bgg_url")
    if not bgg_url and bgg_id:
        bgg_url = f"https://boardgamegeek.com/boardgame/{bgg_id}"
    if bgg_url:
        out["bgg_url"] = bgg_url

    # 覆寫＋說明類欄位
    for key in [
        "name_zh",
        "name_en",
        "alias_zh",
        "description",
        "price_msrp_twd",
        "price_twd",
        "used_price_twd",
        "price_note",
        "used_note",
        "manual_override",
        "stock",
        "image_override",
        "image_version_id",
    ]:
        if key in r and r[key] not in (None, ""):
            out[key] = r[key]

    # 搜尋用關鍵字（如果有的話也保留）
    if "search_keywords" in r and isinstance(r["search_keywords"], list):
        out["search_keywords"] = r["search_keywords"]

    return out


def main() -> None:
    if not BGG_JSON.exists():
        raise SystemExit(f"[ERROR] 找不到 {BGG_JSON}")

    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    with BGG_JSON.open("r", encoding="utf-8") as f:
        rows = json.load(f)

    if not isinstance(rows, list):
        raise SystemExit("[ERROR] bgg_data.json 內容不是 list")

    games = [_compat(r) for r in rows]

    # 完整版（含縮排）
    with OUT_FULL.open("w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, indent=2)

    # 網站用版本（壓縮）
    with OUT_SITE.open("w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, separators=(",", ":"))

    print(f"games_full.json rows={len(games)} → {OUT_FULL}")
    print(f"site/data/games.json rows={len(games)} → {OUT_SITE}")


if __name__ == "__main__":
    main()

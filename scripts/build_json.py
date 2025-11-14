#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
產出兩份：
1) data/games_full.json（完整清單，供檢查）
2) site/data/games.json（網站實際讀取）

功能：
- 舊鍵名相容與欄位補齊（players、time、rating_avg、price_twd 等）
- 統一路徑：所有本地圖片一律輸出為 ../assets/img/xxx
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_IN = ROOT / "data" / "bgg_data.json"
OUT_FULL = ROOT / "data" / "games_full.json"
OUT_SITE = ROOT / "site" / "data" / "games.json"


def _fix_local_path(val: str) -> str:
    """把本地圖片路徑統一轉成 ../assets/img/...，保留 http(s) 不動。"""
    if not isinstance(val, str):
        return val
    s = val.strip()
    if not s:
        return s

    # 遠端網址直接保留
    if s.startswith(("http://", "https://")):
        return s

    # 已經是 ../assets/ 開頭就不再處理
    if s.startswith("../assets/"):
        return s

    # 目前的格式：assets/img/xxx
    if s.startswith("assets/img/"):
        return "../" + s

    # 若是不小心只有 img/xxx
    if s.startswith("img/"):
        return "../assets/" + s

    # 若只有檔名，補成 ../assets/img/xxx
    if "/" not in s:
        return "../assets/img/" + s

    # 其他相對路徑，一律補上 ../，避免被 /site/ 吃掉
    return "../" + s.lstrip("./")


def _normalize_record(r: dict) -> dict:
    """單筆資料相容＋補欄位＋圖片路徑處理。"""
    r = dict(r)

    # ---- ID 相容 ----
    bgg_id = r.get("bgg_id") or r.get("id")
    name = r.get("name") or r.get("name_en") or r.get("name_zh")
    if not r.get("id"):
        if bgg_id and name:
            r["id"] = f"{name}-{bgg_id}"
        elif bgg_id:
            r["id"] = str(bgg_id)
        elif name:
            r["id"] = name

    # ---- 玩家數相容：minplayers / min_players ----
    if "minplayers" in r and "min_players" not in r:
        r["min_players"] = r["minplayers"]
    if "maxplayers" in r and "max_players" not in r:
        r["max_players"] = r["maxplayers"]
    if "min_players" in r and "minplayers" not in r:
        r["minplayers"] = r["min_players"]
    if "max_players" in r and "maxplayers" not in r:
        r["maxplayers"] = r["max_players"]

    mp = r.get("min_players") or r.get("minplayers")
    xp = r.get("max_players") or r.get("maxplayers")
    if not r.get("players") and (mp is not None or xp is not None):
        if mp is None:
            mp = xp
        if xp is None:
            xp = mp
        r["players"] = [mp, xp]

    # ---- 時間相容：minplaytime / min_playtime ----
    if "minplaytime" in r and "min_playtime" not in r:
        r["min_playtime"] = r["minplaytime"]
    if "maxplaytime" in r and "max_playtime" not in r:
        r["max_playtime"] = r["maxplaytime"]
    if "min_playtime" in r and "minplaytime" not in r:
        r["minplaytime"] = r["min_playtime"]
    if "max_playtime" in r and "maxplaytime" not in r:
        r["maxplaytime"] = r["max_playtime"]

    # ---- 評分相容：usersrated / users_rated；rating / rating_avg ----
    if r.get("usersrated") is None and r.get("users_rated") is not None:
        r["usersrated"] = r["users_rated"]
    if r.get("users_rated") is None and r.get("usersrated") is not None:
        r["users_rated"] = r["usersrated"]

    if r.get("rating_avg") is None and r.get("rating") is not None:
        try:
            r["rating_avg"] = float(r["rating"])
        except (TypeError, ValueError):
            pass
    if r.get("rating") is None and r.get("rating_avg") is not None:
        r["rating"] = r["rating_avg"]

    # ---- Weight 相容：weight / weight_avg ----
    if r.get("weight") is None and r.get("weight_avg") is not None:
        r["weight"] = r["weight_avg"]

    # ---- 價格相容：price / price_twd；price_used / used_price_twd ----
    if r.get("price_twd") is None and r.get("price") is not None:
        r["price_twd"] = r["price"]
    if r.get("price") is None and r.get("price_twd") is not None:
        r["price"] = r["price_twd"]

    if r.get("used_price_twd") is None and r.get("price_used") is not None:
        r["used_price_twd"] = r["price_used"]
    if r.get("price_used") is None and r.get("used_price_twd") is not None:
        r["price_used"] = r["used_price_twd"]

    # ---- 機制相容：mechanics / mechanisms ----
    if "mechanisms" not in r and "mechanics" in r:
        r["mechanisms"] = r["mechanics"]
    if "mechanics" not in r and "mechanisms" in r:
        r["mechanics"] = r["mechanisms"]

    # ---- 中文欄位命名相容（若你有用 CamelCase）----
    if "categories_zh" not in r and "categoriesZh" in r:
        r["categories_zh"] = r["categoriesZh"]
    if "mechanisms_zh" not in r and "mechanismsZh" in r:
        r["mechanisms_zh"] = r["mechanismsZh"]

    # ---- 圖片路徑處理 ----
    ov = (r.get("image_override") or "").strip()
    if ov:
        new_ov = _fix_local_path(ov)
        r["image_override"] = new_ov
        if not r.get("image_local"):
            # 給一個統一的本地欄位，前端 imgCandidates 也會吃得到
            r["image_local"] = new_ov

    # 決定最終顯示用 image：本地優先 → 遠端 fallback
    image = None
    if r.get("image_local"):
        image = _fix_local_path(r["image_local"])
    elif r.get("image_override"):
        image = _fix_local_path(r["image_override"])
    else:
        for key in ("image", "image_url", "thumbnail", "thumb_url"):
            v = r.get(key)
            if not v:
                continue
            if isinstance(v, str) and not v.startswith(("http://", "https://")):
                v = _fix_local_path(v)
            image = v
            break

    if image:
        r["image"] = image

    return r


def main() -> int:
    if not DATA_IN.exists():
        print(f"[build_json] ERROR: {DATA_IN} 不存在，請先跑上游腳本（resolve_bgg / apply_taxonomy_and_price 等）")
        return 1

    rows = json.loads(DATA_IN.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        print("[build_json] ERROR: bgg_data.json 格式不是 list")
        return 1

    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        out.append(_normalize_record(r))

    # 1) 完整版（debug 用）
    OUT_FULL.parent.mkdir(parents=True, exist_ok=True)
    OUT_FULL.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    # 2) 給網站用的版本（目前直接同一份，前端只會用到部份欄位）
    OUT_SITE.parent.mkdir(parents=True, exist_ok=True)
    OUT_SITE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    print(f"games_full.json rows={len(out)} ; wrote → {OUT_FULL}")
    print(f"site/data/games.json rows={len(out)} ; wrote → {OUT_SITE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

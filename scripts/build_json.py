#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
產出兩份：
1) data/games_full.json（完整清單，供檢查）
2) site/data/games.json（網站實際讀取）

功能：
- 舊鍵名相容與欄位補齊（players、time、rating_avg、price_twd 等）
- 評分／權重／價格欄位對齊
- 圖片路徑統一成 assets/img/xxx（讓 /site/ 下用 assets/img/xxx 即可找到 site/assets/img/xxx）
"""

import json
import pathlib
from typing import Any, Dict

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_IN = ROOT / "data" / "bgg_data.json"
OUT_FULL = ROOT / "data" / "games_full.json"
OUT_SITE = ROOT / "site" / "data" / "games.json"


def _norm_local_img_path(val: str) -> str:
    """
    把各種本地圖片路徑統一轉成 assets/img/xxx：

    支援處理：
    - "site/assets/img/xxx.jpg"  → "assets/img/xxx.jpg"
    - "../assets/img/xxx.jpg"    → "assets/img/xxx.jpg"
    - "assets/img/xxx.jpg"       → "assets/img/xxx.jpg"
    - "img/xxx.jpg"              → "assets/img/xxx.jpg"
    - "xxx.jpg"                  → "assets/img/xxx.jpg"
    - http(s)://...              → 保留原樣（遠端圖）
    """
    if not isinstance(val, str):
        return val
    s = val.strip()
    if not s:
        return s

    # 遠端網址不動
    if s.startswith(("http://", "https://")):
        return s

    s = s.replace("\\", "/")

    # 移除前面的 "site/"
    if s.startswith("site/"):
        s = s[len("site/") :]

    # "../assets/img/xxx" → "assets/img/xxx"
    if s.startswith("../assets/img/"):
        # 去掉前導 "../"
        while s.startswith("../"):
            s = s[3:]

    # "assets/img/xxx" 直接接受
    if s.startswith("assets/img/"):
        return s

    # "img/xxx" → "assets/img/xxx"
    if s.startswith("img/"):
        return "assets/" + s

    # 單純檔名 → "assets/img/xxx"
    if "/" not in s:
        return "assets/img/" + s

    # 其他奇怪相對路徑，先原樣交給前端 absUrl，再說
    return s


def _normalize_record(r: Dict[str, Any]) -> Dict[str, Any]:
    """單筆紀錄：鍵名相容、欄位補齊、圖片路徑整理。"""
    r = dict(r)

    # ---- ID 與名稱 ----
    bgg_id = r.get("bgg_id") or r.get("id")
    name_en = r.get("name") or r.get("name_en")
    name_zh = r.get("name_zh")
    if not r.get("id"):
        if bgg_id and name_en:
            r["id"] = f"{name_en}-{bgg_id}"
        elif bgg_id:
            r["id"] = str(bgg_id)
        elif name_en or name_zh:
            r["id"] = name_en or name_zh

    # ---- 玩家數：minplayers / min_players ----
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

    # ---- 時間：minplaytime / min_playtime ----
    if "minplaytime" in r and "min_playtime" not in r:
        r["min_playtime"] = r["minplaytime"]
    if "maxplaytime" in r and "max_playtime" not in r:
        r["max_playtime"] = r["maxplaytime"]
    if "min_playtime" in r and "minplaytime" not in r:
        r["minplaytime"] = r["min_playtime"]
    if "max_playtime" in r and "maxplaytime" not in r:
        r["maxplaytime"] = r["max_playtime"]

    # ---- 評分：usersrated / users_rated；rating / rating_avg ----
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

    # ---- weight / weight_avg ----
    if r.get("weight") is None and r.get("weight_avg") is not None:
        r["weight"] = r["weight_avg"]

    # ---- 價格：price / price_twd；price_used / used_price_twd ----
    if r.get("price_twd") is None and r.get("price") is not None:
        r["price_twd"] = r["price"]
    if r.get("price") is None and r.get("price_twd") is not None:
        r["price"] = r["price_twd"]

    if r.get("used_price_twd") is None and r.get("price_used") is not None:
        r["used_price_twd"] = r["price_used"]
    if r.get("price_used") is None and r.get("used_price_twd") is not None:
        r["price_used"] = r["used_price_twd"]

    # ---- 機制：mechanics / mechanisms ----
    if "mechanisms" not in r and "mechanics" in r:
        r["mechanisms"] = r["mechanics"]
    if "mechanics" not in r and "mechanisms" in r:
        r["mechanics"] = r["mechanisms"]

    # ---- 中文欄位大小寫相容 ----
    if "categories_zh" not in r and "categoriesZh" in r:
        r["categories_zh"] = r["categoriesZh"]
    if "mechanisms_zh" not in r and "mechanismsZh" in r:
        r["mechanisms_zh"] = r["mechanismsZh"]

    # ---- 圖片路徑整理 ----
    ov = (r.get("image_override") or "").strip()
    if ov:
        ov_norm = _norm_local_img_path(ov)
        r["image_override"] = ov_norm
        # 補一個 image_local，讓前端 imgCandidates 也吃得到
        if not r.get("image_local"):
            r["image_local"] = ov_norm

    # 決定最終 image：本地優先 → 遠端 fallback
    image = None
    if r.get("image_local"):
        image = _norm_local_img_path(r["image_local"])
    elif r.get("image_override"):
        image = _norm_local_img_path(r["image_override"])
    else:
        for key in ("image", "image_url", "thumbnail", "thumb_url"):
            v = r.get(key)
            if not v:
                continue
            if isinstance(v, str) and not v.startswith(("http://", "https://")):
                v = _norm_local_img_path(v)
            image = v
            break

    if image:
        r["image"] = image

    return r


def main() -> int:
    if not DATA_IN.exists():
        print(f"[build_json] ERROR: {DATA_IN} 不存在，請先跑 resolve_bgg / apply_taxonomy_and_price 等上游腳本")
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

    # 2) 網站版（暫時直接同一份；稍後由 publish_games 再 copy 一次）
    OUT_SITE.parent.mkdir(parents=True, exist_ok=True)
    OUT_SITE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    print(f"games_full.json rows={len(out)} ; wrote → {OUT_FULL}")
    print(f"site/data/games.json rows={len(out)} ; wrote → {OUT_SITE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

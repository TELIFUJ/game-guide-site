# scripts/build_json.py
# -*- coding: utf-8 -*-
"""
產出兩份：
1) data/games_full.json（完整清單，供檢查）
2) site/data/games.json（網站實際讀取）
並做舊鍵名相容與欄位補齊（players、time、rating_avg 等）
"""
import json, pathlib, math

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

    # 評分統一鍵
    if r.get("rating") is None and r.get("rating_avg") is not None:
        r["rating"] = r.get("rating_avg")
    # 同時輸出新舊兩種命名，避免前端歷史碼失效
    r["rating_avg"]   = r.get("rating")        # 舊碼相容
    r["rating_bayes"] = r.get("rating_bayes")  # 已是既有
    r["users_rated"]  = r.get("usersrated") if r.get("users_rated") is None else r.get("users_rated")
    r["weight_avg"]   = r.get("weight")        # 舊碼相容

    # 影像欄位統一
    img = r.get("image") or r.get("image_url") or r.get("thumbnail") or r.get("thumb_url") or ""
    r["image"] = img

    # 衍生顯示欄位（字串型，方便前端直接印）
    def _rng(lo, hi):
        if lo and hi and lo != hi:
            return f"{lo}–{hi}"
        return f"{lo}" if lo else (f"{hi}" if hi else "")

    r["players_str"] = _rng(r.get("min_players"), r.get("max_players"))
    r["time_str"]    = _rng(r.get("min_playtime"), r.get("max_playtime"))

    # 允許空陣列但不為 None
    r["categories"] = r.get("categories") or []
    r["mechanisms"] = r.get("mechanisms") or []

    # 機制數量（卡片顯示用）
    r["mechanism_count"] = len(r["mechanisms"])

    # 供推薦計算的關鍵詞集合
    r["_reco_keys"] = sorted(set([*r["categories"], *r["mechanisms"]]))

    return r

def main():
    rows = json.loads(DATA_IN.read_text(encoding="utf-8")) if DATA_IN.exists() else []
    fixed = [_compat(x) for x in rows]

    # 完整檔
    OUT_FULL.parent.mkdir(parents=True, exist_ok=True)
    OUT_FULL.write_text(json.dumps(fixed, ensure_ascii=False, indent=2), encoding="utf-8")

    # 網站檔（可直接用完整，或做精簡；這裡直接用）
    OUT_SITE.parent.mkdir(parents=True, exist_ok=True)
    OUT_SITE.write_text(json.dumps(fixed, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"games_full.json rows={len(fixed)} ; wrote → {OUT_FULL}")
    print(f"site/data/games.json rows={len(fixed)} ; wrote → {OUT_SITE}")

if __name__ == "__main__":
    main()

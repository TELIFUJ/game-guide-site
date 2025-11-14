#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
產出兩份：
  1) data/games_full.json（完整清單，供檢查）
  2) site/data/games.json（網站實際讀取，型態必為 list）
規則：
  - 舊→新鍵相容（minplayers→min_players 等）。
  - 圖片欄位優先：image_override（相對路徑）→ assets/img/{id}.ext → image_url。
  - 保留永久需求：rating_bayes、rating_avg、users_rated、weight、mechanism_count。
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_IN = ROOT / "data" / "bgg_data.json"
OUT_FULL = ROOT / "data" / "games_full.json"
OUT_SITE = ROOT / "site" / "data" / "games.json"
IMG_DIR = ROOT / "assets" / "img"

KEEP_KEYS = {
    "id", "name", "year", "min_players", "max_players", "min_playtime", "max_playtime",
    "rating_bayes", "rating_avg", "users_rated", "weight", "mechanism_count",
    "categories", "mechanisms", "mechanics", "price_twd", "image_url", "image_override"
}

IMG_EXTS = [".jpg", ".jpeg", ".png", ".webp"]

def _compat(r: dict) -> dict:
    r = dict(r)
    # 舊→新鍵名相容
    r.setdefault("min_players", r.get("minplayers"))
    r.setdefault("max_players", r.get("maxplayers"))
    r.setdefault("min_playtime", r.get("minplaytime"))
    r.setdefault("max_playtime", r.get("maxplaytime"))
    r.setdefault("rating_avg", r.get("rating"))
    r.setdefault("users_rated", r.get("usersrated") or r.get("users_rated"))
    r.setdefault("weight", r.get("weight_avg") or r.get("weight"))
    r.setdefault("mechanism_count", r.get("mechanisms_count") or r.get("mechanism_count"))
    r.setdefault("mechanisms", r.get("mechanics") or r.get("mechanisms"))
    r.setdefault("categories", r.get("categories"))
    return r

def pick_image(r: dict) -> str:
    # 1) 嚴格尊重 image_override
    override = (r.get("image_override") or "").strip()
    if override:
        # 若未含 assets/ 前綴，補上標準前綴
        if not (override.startswith("assets/") or override.startswith("./assets/")):
            override = str(pathlib.Path("assets") / "img" / override)
        return override

    # 2) 搜尋 assets/img/{id}.ext
    gid = str(r.get("id") or r.get("game_id") or "").strip()
    if gid:
        for ext in IMG_EXTS:
            p = IMG_DIR / f"{gid}{ext}"
            if p.exists() and p.stat().st_size > 0:
                return str(pathlib.Path("assets") / "img" / p.name)

    # 3) 回退遠端 URL
    return r.get("image_url") or r.get("image") or "assets/img/placeholder.svg"

def trim_record(r: dict) -> dict:
    rr = _compat(r)
    image = pick_image(rr)
    out = {k: rr.get(k) for k in KEEP_KEYS if k in rr}
    out["image"] = image
    # 同義欄位維持完整
    out["mechanics"] = rr.get("mechanics") or rr.get("mechanisms") or []
    out["categories"] = rr.get("categories") or []
    # 非空預設
    out.setdefault("rating_bayes", rr.get("rating_bayes") or 0)
    out.setdefault("rating_avg", rr.get("rating_avg") or 0)
    out.setdefault("users_rated", rr.get("users_rated") or 0)
    out.setdefault("weight", rr.get("weight") or 0)
    out.setdefault("mechanism_count", rr.get("mechanism_count") or (len(out["mechanics"]) if isinstance(out["mechanics"], list) else 0))
    return out

def main():
    ROOT.joinpath("site", "data").mkdir(parents=True, exist_ok=True)
    if not DATA_IN.exists():
        print(f"[build_json] 找不到 {DATA_IN}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(DATA_IN.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        # 保險絲：若誤寫成 dict，轉為 list(values)
        data = list(data.values())

    out = [trim_record(r) for r in data]
    OUT_FULL.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_SITE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"games_full.json rows={len(out)} ; wrote → {OUT_FULL}")
    print(f"site/data/games.json rows={len(out)} ; wrote → {OUT_SITE}")

if __name__ == "__main__":
    main()

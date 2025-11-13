# scripts/build_json.py
# -*- coding: utf-8 -*-
"""
產出兩份：
1) data/games_full.json（完整檢查）
2) site/data/games.json（網站讀取）
維持欄位相容（players、time、rating_avg 等）。
"""
import json, pathlib, re, hashlib, unicodedata
ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_IN  = ROOT / "data" / "bgg_data.json"
OUT_FULL = ROOT / "data" / "games_full.json"
OUT_SITE = ROOT / "site" / "data" / "games.json"

def _norm_name(s: str) -> str:
    s = s or ""
    return unicodedata.normalize("NFKC", s).strip()

def _players_row(r):
    mi = r.get("minplayers") or r.get("min_players")
    ma = r.get("maxplayers") or r.get("max_players")
    if mi and ma and mi != ma: return f"{mi}–{ma}人"
    if mi: return f"{mi}人"
    if ma: return f"{ma}人"
    return ""

def _time_row(r):
    mi = r.get("minplaytime") or r.get("min_playtime")
    ma = r.get("maxplaytime") or r.get("max_playtime")
    if mi and ma and mi != ma: return f"{mi}–{ma}分"
    if mi: return f"{mi}分"
    if ma: return f"{ma}分"
    return ""

def _to_float(x):
    try:
        if x in (None, "", "N/A"): return None
        return float(x)
    except Exception:
        return None

def _slug(s: str) -> str:
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff\- ]+", "", s)
    s = re.sub(r"\s+", "-", s.strip()).lower()
    return s[:120] or "n"

def _ensure_fields(r: dict) -> dict:
    """鍵名相容 & 補齊衍生欄位"""
    r = dict(r)
    # bgg id
    r["bgg_id"] = r.get("bgg_id") or r.get("id")
    # 相容鍵
    r.setdefault("min_players", r.get("minplayers"))
    r.setdefault("max_players", r.get("maxplayers"))
    r.setdefault("min_playtime", r.get("minplaytime"))
    r.setdefault("max_playtime", r.get("maxplaytime"))

    # 評分相容：rating=玩家平均；rating_bayes=Bayes 平均
    rating = _to_float(r.get("rating"))
    rating_avg = _to_float(r.get("rating_avg"))
    if rating_avg is None and rating is not None:
        rating_avg = rating
    r["rating_avg"] = rating_avg
    r["rating"] = rating_avg  # 舊前端相容
    r["rating_bayes"] = _to_float(r.get("rating_bayes"))
    r["users_rated"] = r.get("users_rated") or r.get("usersrated")

    # 重量
    r["weight_avg"] = _to_float(r.get("weight")) or _to_float(r.get("weight_avg"))

    # players/time 文案
    r["players_text"] = _players_row(r)
    r["time_text"]    = _time_row(r)

    # 分類/機制
    cats = [c for c in (r.get("categories") or []) if c]
    mechs = [m for m in (r.get("mechanisms") or []) if m]
    r["categories"] = cats
    r["mechanisms"] = mechs
    r["mechanism_count"] = len(mechs)

    # 名稱與 slug
    name = _norm_name(r.get("name") or "")
    year = r.get("year")
    r["name"] = name
    r["title"] = f"{name}{(' ('+str(year)+')') if year else ''}"
    base_for_slug = f"{name}-{r['bgg_id']}"
    # 如 image_override 變化，讓卡片 slug 穩定
    ov = r.get("image_override") or ""
    md5 = hashlib.md5(ov.encode("utf-8")).hexdigest()[:6] if ov else "na"
    r["slug"] = f"{_slug(base_for_slug)}-{md5}"
    return r

def main():
    rows = json.loads(DATA_IN.read_text(encoding="utf-8")) if DATA_IN.exists() else []
    out = [_ensure_fields(r) for r in rows]
    OUT_FULL.parent.mkdir(parents=True, exist_ok=True)
    OUT_SITE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FULL.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_SITE.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"games_full.json rows={len(out)} ; wrote → {OUT_FULL}")
    print(f"site/data/games.json rows={len(out)} ; wrote → {OUT_SITE}")

if __name__ == "__main__":
    main()

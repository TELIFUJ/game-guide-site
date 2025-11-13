# scripts/build_json.py
import json, re
from pathlib import Path

IN  = Path("data/bgg_data.json")
OUT = Path("data/games_full.json")
SITE_OUT = Path("site/data/games.json")
SITE_OUT.parent.mkdir(parents=True, exist_ok=True)

def _compat(r: dict) -> dict:
    r = dict(r or {})

    # ---- 保留原始鍵（若不存在則補齊為 None）----
    for k in ("year","minplayers","maxplayers","minplaytime","maxplaytime","rating","usersrated"):
        r.setdefault(k, r.get(k, None))

    # ---- 新 → 舊鍵名（相容前端舊讀法）----
    r.setdefault("min_players",  r.get("minplayers"))
    r.setdefault("max_players",  r.get("maxplayers"))
    r.setdefault("min_playtime", r.get("minplaytime"))
    r.setdefault("max_playtime", r.get("maxplaytime"))
    r.setdefault("rating_avg",   r.get("rating"))
    r.setdefault("users_rated",  r.get("usersrated"))

    # 影像相容
    if not r.get("image_url"):
        r["image_url"] = (r.get("image") or r.get("thumbnail") or r.get("thumb_url") or "") or ""
    if not r.get("thumb_url"):
        r["thumb_url"] = (r.get("thumbnail") or r.get("image") or r.get("image_url") or "") or ""

    # 類別／機制陣列
    r["categories"] = [x for x in (r.get("categories") or []) if isinstance(x, str) and x.strip()]
    r["mechanisms"] = [x for x in (r.get("mechanisms") or []) if isinstance(x, str) and x.strip()]

    # 顯示用（卡片）——可被前端直接使用
    def _fmt_players(a,b):
        try:
            if a and b and a!=b: return f"{a}–{b}人"
            if a and not b: return f"{a}人"
            if not a and b: return f"{b}人"
        except: pass
        return None
    def _fmt_time(a,b):
        try:
            if a and b and a!=b: return f"{a}–{b}分"
            if a and not b: return f"{a}分"
            if not a and b: return f"{b}分"
        except: pass
        return None

    r["players_text"] = _fmt_players(r.get("minplayers"), r.get("maxplayers"))
    r["playtime_text"] = _fmt_time(r.get("minplaytime"), r.get("maxplaytime"))

    return r

def main():
    rows = json.loads(IN.read_text(encoding="utf-8")) if IN.exists() else []
    rows = [_compat(x) for x in rows]

    # 排序：以評分/人數 → 年份 → id
    def _score(x):
        return (
            -(x.get("usersrated") or 0),
            -(x.get("rating") or 0.0),
            -(x.get("year") or 0),
            x.get("id") or x.get("bgg_id") or 0
        )
    rows.sort(key=_score)

    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    SITE_OUT.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print(f"games_full.json rows={len(rows)} ; wrote → {OUT}")
    print(f"site/data/games.json rows={len(rows)} ; wrote → {SITE_OUT}")

if __name__ == "__main__":
    main()

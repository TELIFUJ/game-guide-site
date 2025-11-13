# -*- coding: utf-8 -*-
"""
Build final game dataset.
- 讀取 data/bgg_data.json（已由 apply_taxonomy_and_price.py 合併價格與覆蓋欄位）
- 補齊相容鍵（min_players / rating_avg…）
- 正規化圖片、連結、搜尋鍵
- 輸出 data/games_full.json
"""

import os
import re
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

IN_FILE  = Path("data/bgg_data.json")
OUT_FILE = Path("data/games_full.json")

# 允許的最小筆數（避免誤刪）
BUILD_MIN_ITEMS = int(os.getenv("BUILD_MIN_ITEMS", "0"))

# -----------------------------
# Utilities
# -----------------------------

def _compat(r: Dict[str, Any]) -> Dict[str, Any]:
    """新→舊鍵名的相容層，避免前端讀不到值。"""
    r = dict(r)

    # 新 → 舊鍵名
    r.setdefault("min_players",  r.get("minplayers"))
    r.setdefault("max_players",  r.get("maxplayers"))
    r.setdefault("min_playtime", r.get("minplaytime"))
    r.setdefault("max_playtime", r.get("maxplaytime"))
    r.setdefault("rating_avg",   r.get("rating"))
    r.setdefault("users_rated",  r.get("usersrated"))

    # 影像相容
    if not r.get("image_url"):
        r["image_url"] = (r.get("image") or r.get("thumbnail") or r.get("thumb_url") or "") or None
    if not r.get("thumb_url"):
        r["thumb_url"] = (r.get("thumbnail") or r.get("image") or r.get("image_url") or "") or None

    # ID 相容
    if not r.get("bgg_id") and r.get("id"):
        r["bgg_id"] = r.get("id")

    return r


def _slug(text: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", text).strip("-").lower()
    if not base:
        base = "game"
    return base


def _label_range(a: Optional[int], b: Optional[int], unit: str) -> Optional[str]:
    if a and b and a != b:
        return f"{a}–{b}{unit}"
    if a and (not b or a == b):
        return f"{a}{unit}"
    if b and not a:
        return f"{b}{unit}"
    return None


def _choose_name(r: Dict[str, Any]) -> str:
    # 中文優先（若有 name_zh / alias_zh），否則英名或原始 name
    for k in ("name_zh", "name", "name_en", "name_en_override"):
        v = (r.get(k) or "").strip()
        if v:
            return v
    return f"BGG #{r.get('bgg_id') or r.get('id')}"


def _bgg_url(r: Dict[str, Any]) -> Optional[str]:
    if r.get("bgg_url_override"):
        return r["bgg_url_override"]
    bid = r.get("bgg_id") or r.get("id")
    if not bid:
        return None
    return f"https://boardgamegeek.com/boardgame/{bid}"


def _norm_image(r: Dict[str, Any]) -> Dict[str, Any]:
    """尊重 image_override / image_version_id；若有覆蓋就替換 image_url/thumb_url。"""
    out = dict(r)
    ov = (out.get("image_override") or "").strip()
    if ov:
        out["image_url"] = ov
        out["thumb_url"] = ov
        return out
    # 若 fetch_version_image.py 成功，資料上會帶 image_version_used 與新的 image_url
    # 這裡只做落地保險：若 image_url 空但 thumbnail 有值，互補一次。
    if not out.get("image_url") and out.get("thumbnail"):
        out["image_url"] = out["thumbnail"]
    if not out.get("thumb_url") and out.get("image_url"):
        out["thumb_url"] = out["image_url"]
    return out


def _keywords(r: Dict[str, Any]) -> List[str]:
    ks: List[str] = []
    def add(v):
        if not v: return
        if isinstance(v, str):
            vv = v.strip()
            if vv and vv not in ks:
                ks.append(vv)
        elif isinstance(v, list):
            for x in v:
                add(x)
    for k in ("name_zh", "alias_zh", "name_en", "name", "category_zh"):
        add(r.get(k))
    add(r.get("categories") or [])
    add(r.get("mechanisms") or [])
    # 玩家數/時間/年份關鍵字
    for k in ("year", "min_players", "max_players", "min_playtime", "max_playtime"):
        v = r.get(k)
        if isinstance(v, int):
            add(str(v))
    return ks


def _hash_for_image_override(r: Dict[str, Any]) -> Optional[str]:
    """若有 image_override，產生穩定指紋（供前端快取破壞用）。"""
    ov = (r.get("image_override") or "").strip()
    if not ov:
        return None
    return hashlib.md5(ov.encode("utf-8")).hexdigest()[:10]


# -----------------------------
# Build
# -----------------------------

def main() -> None:
    if not IN_FILE.exists():
        OUT_FILE.write_text("[]", encoding="utf-8")
        print("No input file; wrote empty games_full.json")
        return

    rows: List[Dict[str, Any]] = json.loads(IN_FILE.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        rows = []

    # 1) 相容層
    rows = [_compat(x) for x in rows]

    out: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        rr = dict(r)

        # 2) 影像正規化（尊重 override）
        rr = _norm_image(rr)

        # 3) 文字與衍生欄位
        rr["display_name"]   = _choose_name(rr)
        rr["players_label"]  = _label_range(rr.get("min_players"), rr.get("max_players"), "人")
        rr["time_label"]     = _label_range(rr.get("min_playtime"), rr.get("max_playtime"), "分")
        rr["bgg_url"]        = _bgg_url(rr)
        rr["image_override_sig"] = _hash_for_image_override(rr)

        # 4) 搜尋鍵
        rr["search_keywords"] = _keywords(rr)

        # 5) slug（可供前端路由）
        base = rr["display_name"]
        rr["slug"] = _slug(base)

        # 6) 精簡：確保站內必需欄位都在
        keep_keys = {
            "bgg_id","id","display_name","name_zh","name_en","alias_zh","year",
            "min_players","max_players","min_playtime","max_playtime",
            "players_label","time_label",
            "weight","rating_avg","users_rated",
            "categories","mechanisms","category_zh",
            "price_twd","used_price_twd","price_msrp_twd","price_note","used_note","stock",
            "manual_override","description",
            "image_url","thumb_url","image_override","image_override_sig","image_version_id","image_version_used",
            "link_override","bgg_url_override","bgg_url",
            "search_keywords","slug","source"
        }
        # 補齊 id/bgg_id
        if not rr.get("bgg_id") and rr.get("id"):
            rr["bgg_id"] = rr["id"]

        rr = {k: rr.get(k) for k in keep_keys if k in rr}
        out.append(rr)

    # 7) 去重（以 bgg_id / id）
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for r in out:
        key = r.get("bgg_id") or r.get("id")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    # 8) 基本排序：有評分者數→評分→年分→名稱
    def _score_key(x: Dict[str, Any]):
        return (
            -(x.get("users_rated") or 0),
            -(x.get("rating_avg") or 0.0),
            -(x.get("year") or 0),
            (x.get("display_name") or "")
        )
    deduped.sort(key=_score_key)

    # 9) Guard
    if BUILD_MIN_ITEMS and len(deduped) < BUILD_MIN_ITEMS:
        # 保守：若數量太少，保留舊檔避免整站清空
        print(f"FETCH GUARD: only {len(deduped)} (<{BUILD_MIN_ITEMS}); keep previous {OUT_FILE}")
        if OUT_FILE.exists():
            print("Keep previous games_full.json")
            return

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"games_full.json rows={len(deduped)} ; wrote → {OUT_FILE}")


if __name__ == "__main__":
    main()

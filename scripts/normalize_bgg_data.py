# scripts/normalize_bgg_data.py
# -*- coding: utf-8 -*-
import json, re, urllib.parse, datetime
from pathlib import Path

IN  = Path("data/bgg_data.json")
OUT = Path("data/bgg_data.json")  # 就地覆寫

def _as_list(v):
    if v is None: return []
    return v if isinstance(v, list) else [v]

def _dedup(xs):
    seen=set(); out=[]
    for x in xs:
        if x is None: continue
        s=str(x).strip()
        if not s or s in seen: continue
        seen.add(s); out.append(s)
    return out

def _map_number(v, t):
    if v in (None, "", "N/A"): return None
    try:
        if t is int:   return int(float(v))
        if t is float: return float(v)
    except: return None
    return None

def _with_cache_param(url: str, ver: str|int|None):
    if not url or not ver: return url
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qsl(u.query, keep_blank_values=True)
    if any(k.lower()=="v" for k,_ in q): return url
    q.append(("v", str(ver)))
    return urllib.parse.urlunsplit((u.scheme,u.netloc,u.path,urllib.parse.urlencode(q),u.fragment))

def pick_image(r: dict) -> str:
    ver = r.get("image_version_id") or r.get("image_version_used")
    ovr = (r.get("image_override") or "").strip()
    # 有 override：優先使用前序已寫入的 r["image"]；沒有就回 raw override＋?v=
    if ovr:
        if r.get("image"):
            return r["image"]
        return _with_cache_param(ovr, ver)
    # 無 override：沿用 r["image"]（可能是版本圖/本地縮圖），否則回退
    return r.get("image") or r.get("image_url") or r.get("thumbnail") or r.get("thumb_url") or ""

def norm_row(r: dict) -> dict:
    rr = dict(r)  # copy
    bid = rr.get("bgg_id") or rr.get("id") or rr.get("thing_id")
    try:
        bid = int(float(bid)) if bid not in (None, "") else None
    except: bid = None
    rr["bgg_id"] = bid

    # 名稱（不破壞現有中文）
    rr["name_en"] = rr.get("name_en_override") or rr.get("name_en") or rr.get("name") or rr.get("bgg_query") or ""
    rr["name_zh"] = rr.get("name_zh") or ""

    # 分類／機制（EN 原樣＋中文映射結果沿用現有欄位）
    rr["categories"]   = _dedup(_as_list(rr.get("categories")))
    rr["mechanics"]    = _dedup(_as_list(rr.get("mechanics")))
    rr["categories_zh"]= _dedup(_as_list(rr.get("categories_zh")))
    rr["mechanics_zh"] = _dedup(_as_list(rr.get("mechanics_zh")))

    # 版本圖：尊重前序；必要時對 override 補 ?v=
    rr["image"] = pick_image(rr)

    # 數值欄位統一型別
    rr["weight"]     = _map_number(rr.get("weight") or rr.get("averageweight"), float)
    rr["rating"]     = _map_number(rr.get("rating") or rr.get("rating_avg"), float)
    rr["usersrated"] = _map_number(rr.get("usersrated"), int)
    rr["rank_overall"]= _map_number(rr.get("rank_overall"), int)

    # BGG URL 補齊
    if bid and not rr.get("bgg_url"):
        rr["bgg_url"] = f"https://boardgamegeek.com/boardgame/{bid}"

    # 搜尋關鍵字（不覆蓋既有，補中文別名、分類、機制）
    kw = set()
    for s in _as_list(rr.get("search_keywords")): 
        if s: kw.add(str(s).strip())
    for s in _as_list(rr.get("alias_zh"))+_as_list(rr.get("aliases_zh")):
        if s: kw.add(str(s).strip())
    for s in rr.get("categories_zh", []): 
        if s: kw.add(s)
    for s in rr.get("mechanics_zh", []): 
        if s: kw.add(s)
    if kw: rr["search_keywords"] = sorted(kw)

    # 輕度清理多餘鍵名（可保留原始以利除錯；若要刪除，放在這）
    # for k in ["averageweight","rating_avg","thumbnail","thing_id"]: rr.pop(k, None)

    return rr

def main():
    if not IN.exists():
        raise SystemExit("No data/bgg_data.json to normalize.")
    rows = json.loads(IN.read_text(encoding="utf-8"))
    out  = [norm_row(r) for r in rows if isinstance(r, dict)]
    # 穩健排序：用 usersrated / rating / bgg_id
    out.sort(key=lambda x: (-(x.get("usersrated") or 0), -(x.get("rating") or 0.0), (x.get("bgg_id") or 0)))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"normalize_bgg_data: {len(out)} rows normalized at {datetime.date.today().isoformat()}.")

if __name__ == "__main__":
    main()

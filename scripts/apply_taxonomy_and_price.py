# scripts/apply_taxonomy_and_price.py
import re, json
from pathlib import Path

BGG_INOUT = Path("data/bgg_data.json")
IDS_JSON  = Path("data/bgg_ids.json")

def load_rows():
    if not BGG_INOUT.exists():
        raise SystemExit("no data/bgg_data.json")
    return json.loads(BGG_INOUT.read_text(encoding="utf-8"))

def load_ids_json():
    if not IDS_JSON.exists():
        return {}
    data = json.loads(IDS_JSON.read_text(encoding="utf-8"))
    out = {}
    for r in data if isinstance(data, list) else []:
        bid = r.get("bgg_id")
        if bid is None: 
            continue
        try:
            out[int(bid)] = r
        except Exception:
            pass
    return out

MERGE_KEYS = [
  "name_zh","name_en_override","alias_zh","category_zh",
  "price_msrp_twd","price_twd","used_price_twd",
  "price_note","used_note","manual_override","stock","description",
  "image_override","image_version_id","link_override","bgg_url_override"
]

_PRICE_KEYS = {"price_twd","used_price_twd","price_msrp_twd"}

def _first_int(s):
    if s is None: 
        return None
    if isinstance(s, (int, float)):
        try:
            v = int(float(s))
            return v if v > 0 else None
        except Exception:
            return None
    s = str(s)
    # 取區間最低，例如 "300~500" 或 "300-500"
    m = re.search(r"(\d{2,6})", s.replace(",", ""))
    return int(m.group(1)) if m else None

def _norm_price(v):
    return _first_int(v)

def enrich_urls(r):
    bid = r.get("bgg_id") or r.get("id")
    if bid and not r.get("bgg_url"):
        r["bgg_url"] = f"https://boardgamegeek.com/boardgame/{bid}"
    if r.get("bgg_url_override"):
        r["bgg_url"] = r["bgg_url_override"]
    if r.get("link_override"):
        r["link_url"] = r["link_override"]
    return r

def enrich_search_keywords(r):
    ks = []
    for k in ("name","name_zh","name_en_override","alias_zh"):
        v = r.get(k)
        if v: 
            ks.append(str(v))
    for arrk in ("categories","mechanisms"):
        for x in (r.get(arrk) or []):
            if x: ks.append(str(x))
    r["search_keywords"] = list({x.lower() for x in ks})
    return r

def main():
    rows = load_rows()
    ids_map = load_ids_json()

    out = []
    for r in rows:
        rr = dict(r)
        # 確保有 bgg_id
        bid = rr.get("bgg_id") or rr.get("id")
        try:
            bid = int(bid) if bid is not None else None
        except Exception:
            bid = None
        if bid and "bgg_id" not in rr:
            rr["bgg_id"] = bid

        # ===== 合併（覆蓋／帶入） =====
        if bid and bid in ids_map:
            src = ids_map[bid]
            for k in MERGE_KEYS:
                v = src.get(k)
                if v not in (None, ""):
                    rr[k] = v

        # ===== 價格正規化 =====
        for k in list(_PRICE_KEYS):
            if rr.get(k) not in (None, ""):
                rr[k] = _norm_price(rr.get(k))

        # ===== 圖片處理（尊重 override；version 由後續腳本補）=====
        if rr.get("image_override"):
            rr["image_url"] = rr["image_override"]
        else:
            # 若前一步 parser 只有 image/thumbnail，也補齊兼容欄位
            base_img = (rr.get("image") or rr.get("thumbnail") or "").strip()
            base_th  = (rr.get("thumbnail") or rr.get("image") or "").strip()
            if base_img and not rr.get("image_url"): rr["image_url"] = base_img
            if base_th  and not rr.get("thumb_url"): rr["thumb_url"]  = base_th

        # ===== URL 與關鍵字 =====
        rr = enrich_urls(rr)
        rr = enrich_search_keywords(rr)

        out.append(rr)

    BGG_INOUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"apply_taxonomy_and_price: merged {len(out)} rows")

if __name__ == "__main__":
    main()

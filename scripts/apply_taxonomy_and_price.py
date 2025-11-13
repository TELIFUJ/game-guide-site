# scripts/apply_taxonomy_and_price.py
import json, re, csv, unicodedata
from pathlib import Path
from typing import Dict, List, Any, Optional

BASE = Path("data")
BGG_INOUT = BASE / "bgg_data.json"
IDS_JSON  = BASE / "bgg_ids.json"
MECH_MAP  = BASE / "mechanism_map_zh.csv"
CAT_MAP   = BASE / "category_map_zh.csv"

MERGE_KEYS = [
  "name_zh","name_en_override","alias_zh","category_zh",
  "price_msrp_twd","price_twd","used_price_twd",
  "price_note","used_note","manual_override","stock","description",
  "image_override","image_version_id","link_override","bgg_url_override"
]

def _read_json(path: Path, default):
    if not path.exists(): return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def _write_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def _to_int(s) -> Optional[int]:
    if s is None: return None
    if isinstance(s, (int, float)): 
        try: return int(s)
        except: return None
    t = str(s)
    t = t.replace(",", "").replace("_","").replace("NTD","").replace("TWD","").replace("$","").strip()
    t = re.sub(r"[^\d\-]", "", t)
    try:
        if t == "" or t == "-": return None
        return int(t)
    except:
        return None

def _norm_price(x):
    v=_to_int(x)
    return v if (v is not None and v >= 0) else None

def _uniq(seq: List[Any]) -> List[Any]:
    out=[]; seen=set()
    for x in seq:
        if x is None: continue
        k=str(x).strip()
        if not k: continue
        if k not in seen:
            seen.add(k); out.append(k)
    return out

def _load_map_csv(path: Path, key_col: str, val_col: str) -> Dict[str,str]:
    if not path.exists(): return {}
    m={}
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            k=(row.get(key_col) or "").strip()
            v=(row.get(val_col) or "").strip()
            if k and v:
                m[k] = v
    return m

def _norm_str(s: Optional[str]) -> Optional[str]:
    if s is None: return None
    t = unicodedata.normalize("NFKC", str(s)).strip()
    return t if t else None

def _keywords(parts: List[str]) -> List[str]:
    bag=[]
    for p in parts:
        if not p: continue
        t=unicodedata.normalize("NFKC", p)
        t=re.sub(r"[^0-9A-Za-z\u4e00-\u9fff\u3040-\u30ff\u3400-\u4dbf]+"," ", t)
        bag.extend(w for w in t.split() if w)
    # 去重但保留原順序
    seen=set(); out=[]
    for w in bag:
        k=w.lower()
        if k not in seen:
            seen.add(k); out.append(w)
    return out

def load_ids_json() -> Dict[int,Dict[str,Any]]:
    data = _read_json(IDS_JSON, [])
    out={}
    if isinstance(data, list):
        for r in data:
            if not isinstance(r, dict): continue
            bid = r.get("bgg_id") or r.get("id")
            try:
                bid = int(bid)
            except:
                continue
            out[bid] = r
    return out

def main():
    rows = _read_json(BGG_INOUT, [])
    if not isinstance(rows, list):
        print("bgg_data.json not a list; abort.")
        return

    ids_map = load_ids_json()
    mech_map = _load_map_csv(MECH_MAP, "bgg_mechanism_en", "mechanism_zh")
    cat_map  = _load_map_csv(CAT_MAP,  "bgg_category_en",  "category_zh")

    out=[]
    miss_cnt={"price_twd":0,"used_price_twd":0}
    for r in rows:
        if not isinstance(r, dict): continue
        rr = dict(r)

        # 統一 bgg_id 欄位
        bid = rr.get("bgg_id") or rr.get("id")
        try: bid = int(bid) if bid is not None else None
        except: bid = None
        if bid is not None:
            rr["bgg_id"] = bid
            rr["id"] = bid  # 後續流程用 id

        # 合併 bgg_ids.json（只帶 MERGE_KEYS 且非空值）
        if bid and bid in ids_map:
            src = ids_map[bid]
            for k in MERGE_KEYS:
                v = src.get(k)
                if v not in (None, ""):
                    rr[k] = v

        # 名稱欄位整理
        rr["name"] = _norm_str(rr.get("name")) or _norm_str(rr.get("name_en")) or rr.get("name")
        if rr.get("name_en_override"):
            rr["name_en"] = _norm_str(rr["name_en_override"])
        else:
            rr["name_en"] = rr.get("name")

        # URL（尊重 override/link_override）
        if rr.get("bgg_url_override"):
            rr["bgg_url"] = _norm_str(rr["bgg_url_override"])
        elif rr.get("link_override"):
            rr["bgg_url"] = _norm_str(rr["link_override"])
        elif bid:
            rr["bgg_url"] = f"https://boardgamegeek.com/boardgame/{bid}"

        # 圖片 override
        if rr.get("image_override"):
            img = _norm_str(rr["image_override"])
            if img:
                rr["image"] = img
                rr["thumbnail"] = rr.get("thumbnail") or img

        # 類別/機制：產出中文映射（不覆蓋單欄位 category_zh，保留多值欄位）
        cats = rr.get("categories") or []
        mechs = rr.get("mechanisms") or []
        cats_zh  = [cat_map.get(c, c) for c in cats]
        mechs_zh = [mech_map.get(m, m) for m in mechs]
        rr["categories_zh"] = _uniq(cats_zh)
        rr["mechanisms_zh"] = _uniq(mechs_zh)

        # 價格正規化（TWD）
        for key in ("price_twd","used_price_twd","price_msrp_twd"):
            if key in rr:
                rr[key] = _norm_price(rr.get(key))
            else:
                rr[key] = None
        if rr.get("price_twd") is None: miss_cnt["price_twd"] += 1
        if rr.get("used_price_twd") is None: miss_cnt["used_price_twd"] += 1

        # 關鍵字
        kw = _keywords([
            rr.get("name"), rr.get("name_en"), rr.get("name_zh"), rr.get("alias_zh"),
            *rr.get("categories", []), *rr.get("mechanisms", []),
            *rr.get("categories_zh", []), *rr.get("mechanisms_zh", [])
        ])
        rr["search_keywords"] = kw

        # 其他數值欄位清洗（避免字串化）
        for nkey in ("year","minplayers","maxplayers","minplaytime","maxplaytime","usersrated"):
            v = rr.get(nkey)
            try:
                if v in (None,"","N/A"): rr[nkey]=None
                else: rr[nkey]=int(float(v))
            except:
                rr[nkey]=None
        for fkey in ("rating","rating_bayes","weight"):
            v = rr.get(fkey)
            try:
                if v in (None,"","N/A"): rr[fkey]=None
                else: rr[fkey]=float(v)
            except:
                rr[fkey]=None

        out.append(rr)

    _write_json(BGG_INOUT, out)
    print(f"apply_taxonomy_and_price: rows={len(out)} ; price_twd missing={miss_cnt['price_twd']} ; used_price_twd missing={miss_cnt['used_price_twd']}")
    print("apply_taxonomy_and_price: wrote data/bgg_data.json")

if __name__ == "__main__":
    main()

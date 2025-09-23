import csv, json
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

MANUAL_CSV=Path("data/manual.csv")
BGG_IN=Path("data/bgg_data.json")
BGG_OUT=BGG_IN
CATMAP_CSV=Path("data/category_map_zh.csv")
MECHMAP_CSV=Path("data/mechanism_map_zh.csv")

def _int_or_none(x):
    if x is None: return None
    s=str(x).strip()
    if s=="" or s.lower()=="none": return None
    try: return int(float(s))
    except: return None

def load_manual():
    by_key={}
    by_bid=defaultdict(list)
    if not MANUAL_CSV.exists(): return by_key, by_bid
    with MANUAL_CSV.open(encoding="utf-8-sig") as f:
        r=csv.DictReader(f)
        for row in r:
            row["manual_override"]=int(row.get("manual_override") or 0)
            row["price_msrp_twd"]=_int_or_none(row.get("price_msrp_twd"))
            row["price_twd"]=_int_or_none(row.get("price_twd"))
            row["used_price_twd"]=_int_or_none(row.get("used_price_twd"))
            row["stock"]=_int_or_none(row.get("stock"))
            if row.get("image_version_id") is not None:
                row["image_version_id"]=str(row["image_version_id"]).strip()

            key=str(row.get("bgg_id") or row.get("name_zh") or row.get("bgg_query") or "").strip()
            if key: by_key[key]=row
            bid=str(row.get("bgg_id") or "").strip()
            if bid: by_bid[bid].append(row)
    return by_key, by_bid

def load_map(csv_path, key_en, key_zh):
    m={}
    if not csv_path.exists(): return m
    with csv_path.open(encoding="utf-8-sig") as f:
        r=csv.DictReader(f)
        for row in r:
            en=(row.get(key_en) or "").strip()
            zh=(row.get(key_zh) or "").strip()
            if en: m[en]=zh or en
    return m

OVERRIDE_FIELDS = [
    "name_zh","name_en_override","alias_zh","category_zh",
    "price_msrp_twd","price_twd","used_price_twd","price_note","used_note",
    "manual_override","stock","description",
    "image_override","image_version_id",
]

def apply_one_manual(base_obj, mrow):
    obj = deepcopy(base_obj)
    for fld in OVERRIDE_FIELDS:
        if fld in mrow and mrow[fld] not in (None,""):
            obj[fld] = mrow[fld]
    if obj.get("alias_zh"):
        obj["aliases_zh"]=[x.strip() for x in str(obj["alias_zh"]).split(";") if x.strip()]
    return obj

def main():
    if not BGG_IN.exists():
        print("No data/bgg_data.json; skip apply."); return

    manual_by_key, manual_by_bid = load_manual()
    catmap = load_map(CATMAP_CSV,"bgg_category_en","category_zh")
    mechmap = load_map(MECHMAP_CSV,"bgg_mechanism_en","mechanism_zh")

    base_rows = json.loads(BGG_IN.read_text(encoding="utf-8"))

    out=[]
    rows_by_bid={}
    # 先處理原筆（合併一列 manual）
    for r in base_rows:
        rows_by_bid[str(r.get("bgg_id") or "")]=r
        m=None
        for k in [str(r.get("bgg_id") or ""), str(r.get("name_zh") or ""), str(r.get("bgg_query") or "")]:
            if k and k in manual_by_key: m=manual_by_key[k]; break
        if m:
            r = apply_one_manual(r, m)

        # 中文分類
        if r.get("category_zh"):
            r["categories_zh"]=[x.strip() for x in str(r["category_zh"]).replace("；",";").replace("/", ";").split(";") if x.strip()]
        else:
            en=r.get("categories") or []
            r["categories_zh"]=[catmap.get(x,x) for x in en]

        mechs=r.get("mechanics") or []
        r["mechanics_zh"]=[mechmap.get(x,x) for x in mechs]

        out.append(r)

    # ★ fan-out：manual.csv 同一 bgg_id 還有其他列 → 另複製一張卡
    for bid, mrows in manual_by_bid.items():
        if len(mrows) <= 1: 
            continue
        base = rows_by_bid.get(bid)
        if not base:
            continue
        for mrow in mrows[1:]:
            clone = apply_one_manual(base, mrow)

            if clone.get("category_zh"):
                clone["categories_zh"]=[x.strip() for x in str(clone["category_zh"]).replace("；",";").replace("/", ";").split(";") if x.strip()]
            else:
                en=clone.get("categories") or []
                clone["categories_zh"]=[catmap.get(x,x) for x in en]

            mechs=clone.get("mechanics") or []
            clone["mechanics_zh"]=[mechmap.get(x,x) for x in mechs]

            out.append(clone)

    BGG_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"apply_taxonomy_and_price: total {len(out)}; categories_zh & mechanics_zh applied + fan-out.")
if __name__ == "__main__": main()

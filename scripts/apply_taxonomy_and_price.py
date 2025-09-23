# scripts/apply_taxonomy_and_price.py
import csv, json
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
    d={}
    if not MANUAL_CSV.exists(): return d
    with MANUAL_CSV.open(encoding="utf-8-sig") as f:
        r=csv.DictReader(f)
        for row in r:
            key=str(row.get("bgg_id") or row.get("name_zh") or row.get("bgg_query"))
            if not key: continue
            row["manual_override"]=int(row.get("manual_override") or 0)
            row["price_msrp_twd"]=_int_or_none(row.get("price_msrp_twd"))
            row["price_twd"]=_int_or_none(row.get("price_twd"))
            row["used_price_twd"]=_int_or_none(row.get("used_price_twd"))
            row["stock"]=_int_or_none(row.get("stock"))
            if row.get("image_version_id") is not None:
                row["image_version_id"]=str(row["image_version_id"]).strip()
            d[key]=row   # 單筆覆蓋（回到舊邏輯）
    return d

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

def main():
    if not BGG_IN.exists():
        print("No data/bgg_data.json; skip apply."); return
    manual=load_manual()
    catmap=load_map(CATMAP_CSV,"bgg_category_en","category_zh")
    mechmap=load_map(MECHMAP_CSV,"bgg_mechanism_en","mechanism_zh")

    rows=json.loads(BGG_IN.read_text(encoding="utf-8"))
    out=[]
    for r in rows:
        # 用 bgg_id > name_zh > bgg_query 任何一個 key 命中，就合併那一行（舊邏輯：單筆）
        m=None
        for k in [str(r.get("bgg_id") or ""), str(r.get("name_zh") or ""), str(r.get("bgg_query") or "")]:
            if k and k in manual:
                m=manual[k]; break
        if m:
            for fld in ["name_zh","name_en_override","alias_zh","category_zh","price_msrp_twd",
                        "price_twd","used_price_twd","price_note","used_note","manual_override",
                        "stock","description","image_override","image_version_id"]:
                if fld in m and m[fld] not in (None,""):
                    r[fld]=m[fld]

        # 中文分類
        if r.get("category_zh"):
            r["categories_zh"]=[x.strip() for x in str(r["category_zh"]).replace("；",";").replace("/", ";").split(";") if x.strip()]
        else:
            en=r.get("categories") or []
            r["categories_zh"]=[(catmap.get(x) or x) for x in en]

        # 機制中文
        mechs=r.get("mechanics") or []
        r["mechanics_zh"]=[(mechmap.get(x) or x) for x in mechs]

        if r.get("alias_zh"):
            r["aliases_zh"]=[x.strip() for x in str(r["alias_zh"]).split(";") if x.strip()]

        # 若手動覆蓋了 image_override，先寫進 r.image（build_json 還會再保險一次）
        if r.get("image_override"):
            r["image"]=r["image_override"]

        out.append(r)

    BGG_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"apply_taxonomy_and_price: total {len(out)}; categories_zh & mechanics_zh applied.")

if __name__ == "__main__": main()

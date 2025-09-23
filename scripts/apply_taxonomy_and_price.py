# scripts/apply_taxonomy_and_price.py
import csv, json
from pathlib import Path

MANUAL_CSV=Path("data/manual.csv")
BGG_IN=Path("data/bgg_data.json")
BGG_OUT=BGG_IN
CATMAP_CSV=Path("data/category_map_zh.csv")
MECHMAP_CSV=Path("data/mechanism_map_zh.csv")

INT_FIELDS = {"price_msrp_twd","price_twd","used_price_twd","stock"}

def _int_or_none(x):
    if x is None: return None
    s=str(x).strip()
    if s=="" or s.lower()=="none": return None
    try: return int(float(s))
    except: return None

def load_manual_grouped():
    """
    回傳 dict： key -> [row,row,...]
    key 依序用：bgg_id > name_zh > bgg_query
    支援「同一 key 多列」（fan-out）
    """
    g={}
    if not MANUAL_CSV.exists(): return g
    with MANUAL_CSV.open(encoding="utf-8-sig") as f:
        r=csv.DictReader(f)
        for row in r:
            key = str(row.get("bgg_id") or row.get("name_zh") or row.get("bgg_query") or "").strip()
            if not key: continue

            # 正規化欄位
            row["manual_override"]=int(row.get("manual_override") or 0)
            for k in INT_FIELDS:
                row[k] = _int_or_none(row.get(k))
            if row.get("image_version_id") is not None:
                row["image_version_id"] = str(row["image_version_id"]).strip()
            # 清掉空白
            if row.get("image_override"):
                row["image_override"] = row["image_override"].strip()
            if row.get("edition_key"):
                row["edition_key"] = str(row["edition_key"]).strip()

            g.setdefault(key, []).append(row)
    return g

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
    # 新增：版本鍵
    "edition_key"
]

def _postprocess(r, catmap, mechmap):
    # 中文分類
    if r.get("category_zh"):
        r["categories_zh"]=[x.strip() for x in str(r["category_zh"]).replace("；",";").replace("/", ";").split(";") if x.strip()]
    else:
        en=r.get("categories") or []
        r["categories_zh"]=[catmap.get(x,x) for x in en]

    # 機制中文
    mechs=r.get("mechanics") or []
    r["mechanics_zh"]=[mechmap.get(x,x) for x in mechs]

    # 別名
    if r.get("alias_zh"):
        r["aliases_zh"]=[x.strip() for x in str(r["alias_zh"]).split(";") if x.strip()]

    return r

def main():
    if not BGG_IN.exists():
        print("No data/bgg_data.json; skip apply."); return

    manual_g = load_manual_grouped()
    catmap   = load_map(CATMAP_CSV,"bgg_category_en","category_zh")
    mechmap  = load_map(MECHMAP_CSV,"bgg_mechanism_en","mechanism_zh")

    base = json.loads(BGG_IN.read_text(encoding="utf-8"))
    out = []

    for r in base:
        # 依 key 順序尋找對應的「多列」手動設定（fan-out）
        candidates = None
        for k in [str(r.get("bgg_id") or ""), str(r.get("name_zh") or ""), str(r.get("bgg_query") or "")]:
            if k and k in manual_g:
                candidates = manual_g[k]
                break

        # 沒對應到 → 原樣保留一筆
        if not candidates:
            out.append(_postprocess(dict(r), catmap, mechmap))
            continue

        # 有多列 → 逐列 clone + 覆蓋（每列產一張卡）
        for m in candidates:
            rr = dict(r)
            for fld in OVERRIDE_FIELDS:
                if fld in m and m[fld] not in (None,""):
                    rr[fld] = m[fld]

            # 標記變體歸屬
            rr["is_variant_of"] = r.get("bgg_id")

            # 讓 image_override 永遠優先
            if rr.get("image_override"):
                rr["image"] = rr["image_override"]

            out.append(_postprocess(rr, catmap, mechmap))

    BGG_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"apply_taxonomy_and_price: total {len(out)}; categories_zh & mechanics_zh applied.")

if __name__ == "__main__": main()

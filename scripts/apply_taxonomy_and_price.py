# scripts/apply_taxonomy_and_price.py
import csv, json
from pathlib import Path

MANUAL_CSV = Path("data/manual.csv")
BGG_IN     = Path("data/bgg_data.json")
BGG_OUT    = BGG_IN
CATMAP_CSV = Path("data/category_map_zh.csv")
MECHMAP_CSV= Path("data/mechanism_map_zh.csv")

def _int_or_none(x):
    if x is None: return None
    s=str(x).strip()
    if s=="" or s.lower()=="none": return None
    try: return int(float(s))
    except: return None

def load_manual_rows():
    """
    讀完整個 manual.csv，保留『多列同 bgg_id』，並建立三種索引：
    by_id[str(bgg_id)] -> [rows...]
    by_name[str(name_zh)] -> [rows...]
    by_query[str(bgg_query)] -> [rows...]
    """
    rows = []
    by_id, by_name, by_query = {}, {}, {}
    if not MANUAL_CSV.exists(): 
        return rows, by_id, by_name, by_query

    with MANUAL_CSV.open(encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            # 清洗常用欄位
            row["manual_override"] = int(row.get("manual_override") or 0)
            row["price_msrp_twd"]  = _int_or_none(row.get("price_msrp_twd"))
            row["price_twd"]       = _int_or_none(row.get("price_twd"))
            row["used_price_twd"]  = _int_or_none(row.get("used_price_twd"))
            row["stock"]           = _int_or_none(row.get("stock"))

            if row.get("image_version_id") is not None:
                row["image_version_id"] = str(row["image_version_id"]).strip()

            # 收進 rows 與索引
            rows.append(row)
            if row.get("bgg_id"):
                by_id.setdefault(str(row["bgg_id"]).strip(), []).append(row)
            if row.get("name_zh"):
                by_name.setdefault(str(row["name_zh"]).strip(), []).append(row)
            if row.get("bgg_query"):
                by_query.setdefault(str(row["bgg_query"]).strip(), []).append(row)

    return rows, by_id, by_name, by_query

def load_map(csv_path, key_en, key_zh):
    m = {}
    if not csv_path.exists(): return m
    with csv_path.open(encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            en = (row.get(key_en) or "").strip()
            zh = (row.get(key_zh) or "").strip()
            if en: m[en] = zh or en
    return m

def apply_cn_fields(r, catmap, mechmap):
    # 中文分類
    if r.get("category_zh"):
        r["categories_zh"] = [x.strip() for x in str(r["category_zh"]).replace("；",";").replace("/", ";").split(";") if x.strip()]
    else:
        en = r.get("categories") or []
        r["categories_zh"] = [catmap.get(x, x) for x in en]

    # 機制中文
    mechs = r.get("mechanics") or []
    r["mechanics_zh"] = [mechmap.get(x, x) for x in mechs]

    # 別名
    if r.get("alias_zh"):
        r["aliases_zh"] = [x.strip() for x in str(r["alias_zh"]).split(";") if x.strip()]

def main():
    if not BGG_IN.exists():
        print("No data/bgg_data.json; skip apply."); return

    manual_rows, by_id, by_name, by_query = load_manual_rows()
    catmap = load_map(CATMAP_CSV, "bgg_category_en", "category_zh")
    mechmap= load_map(MECHMAP_CSV, "bgg_mechanism_en","mechanism_zh")

    base = json.loads(BGG_IN.read_text(encoding="utf-8"))
    out  = []

    for r in base:
        bid = r.get("bgg_id")
        key_id   = str(bid).strip() if bid not in (None, "") else ""
        key_name = str(r.get("name_zh") or "").strip()
        key_q    = str(r.get("bgg_query") or "").strip()

        # 找出所有匹配的 manual 列（允許多筆 → fan-out）
        matches = []
        if key_id and key_id in by_id:   matches.extend(by_id[key_id])
        if key_name and key_name in by_name: matches.extend(by_name[key_name])
        if key_q and key_q in by_query:  matches.extend(by_query[key_q])

        # 去重（以物件 id 去重即可）
        seen_ids = set()
        uniq_matches = []
        for m in matches:
            if id(m) in seen_ids: 
                continue
            seen_ids.add(id(m))
            uniq_matches.append(m)

        if not uniq_matches:
            # 沒有 manual → 原樣（但仍補中文欄位）
            rr = dict(r)
            apply_cn_fields(rr, catmap, mechmap)
            out.append(rr)
            continue

        # 有 manual → 為每一條 manual 產生一張卡（clone）
        for m in uniq_matches:
            rr = dict(r)
            # 覆寫欄位（包含 image_override、image_version_id）
            for fld in [
                "name_zh","name_en_override","alias_zh","category_zh",
                "price_msrp_twd","price_twd","used_price_twd","price_note","used_note",
                "manual_override","stock","description",
                "image_override","image_version_id"
            ]:
                if fld in m and m[fld] not in (None, ""):
                    rr[fld] = m[fld]

            # 優先使用 image_override（真正換圖在 build_json 也會再保險一次）
            if rr.get("image_override"):
                rr["image"] = rr["image_override"]

            apply_cn_fields(rr, catmap, mechmap)
            out.append(rr)

    BGG_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"apply_taxonomy_and_price: total {len(out)}; categories_zh & mechanics_zh applied.")

if __name__ == "__main__":
    main()

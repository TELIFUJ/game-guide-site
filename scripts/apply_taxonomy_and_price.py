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
    s = str(x).strip()
    if s=="" or s.lower()=="none": return None
    try: return int(float(s))
    except: return None

def load_manual_grouped():
    """
    讀取 manual.csv，按 key 分組（key = bgg_id > name_zh > bgg_query）
    支援同一 key 多列（fan-out）
    """
    groups = {}  # {key: [row,row,...]}
    if not MANUAL_CSV.exists(): return groups

    with MANUAL_CSV.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            key = str(row.get("bgg_id") or row.get("name_zh") or row.get("bgg_query") or "").strip()
            if not key: 
                continue
            # 正規化欄位型態
            row["manual_override"] = int(row.get("manual_override") or 0)
            row["price_msrp_twd"]  = _int_or_none(row.get("price_msrp_twd"))
            row["price_twd"]       = _int_or_none(row.get("price_twd"))
            row["used_price_twd"]  = _int_or_none(row.get("used_price_twd"))
            row["stock"]           = _int_or_none(row.get("stock"))

            if row.get("image_version_id") is not None:
                row["image_version_id"] = str(row["image_version_id"]).strip()

            groups.setdefault(key, []).append(row)
    return groups

def load_map(csv_path, key_en, key_zh):
    m = {}
    if not csv_path.exists(): return m
    with csv_path.open(encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            en = (row.get(key_en) or "").strip()
            zh = (row.get(key_zh) or "").strip()
            if en:
                m[en] = zh or en
    return m

def _apply_manual_fields(base: dict, m: dict) -> dict:
    """
    依手動欄位覆蓋 base，並處理 image_override 與 image_version_id → 寫入 image
    """
    out = dict(base)
    for fld in [
        "name_zh","name_en_override","alias_zh","category_zh",
        "price_msrp_twd","price_twd","used_price_twd",
        "price_note","used_note","manual_override","stock",
        "description",
        # 圖片控制（優先使用）
        "image_override","image_version_id",
        # 如日後需要可再放 link_override/bgg_url_override 等
    ]:
        if fld in m and m[fld] not in (None, ""):
            out[fld] = m[fld]

    # 別名切陣列
    if out.get("alias_zh"):
        out["aliases_zh"] = [x.strip() for x in str(out["alias_zh"]).split(";") if x.strip()]

    # 只要有 image_override，就直接定案到 image（並加 ?v= 版本字串，防快取）
    img_ovr = (m.get("image_override") or "").strip()
    if img_ovr:
        v = (m.get("image_version_id") or "").strip()
        if v:
            sep = "&" if "?" in img_ovr else "?"
            out["image"] = f"{img_ovr}{sep}v={v}"
        else:
            out["image"] = img_ovr
    # 若沒 override，就保持原本（之後 build_json 仍會 fallback 到 image_url/thumb_url）

    return out

def main():
    if not BGG_IN.exists():
        print("No data/bgg_data.json; skip apply."); return

    manual_groups = load_manual_grouped()
    catmap = load_map(CATMAP_CSV,"bgg_category_en","category_zh")
    mechmap= load_map(MECHMAP_CSV,"bgg_mechanism_en","mechanism_zh")

    rows = json.loads(BGG_IN.read_text(encoding="utf-8"))
    out  = []

    for r in rows:
        # 找到對應這筆 base 的所有手動列（bgg_id > name_zh > bgg_query）
        keys = [str(r.get("bgg_id") or ""), str(r.get("name_zh") or ""), str(r.get("bgg_query") or "")]
        matched = None
        for k in keys:
            if k and k in manual_groups:
                matched = manual_groups[k]
                break

        if matched:
            # 有多列就 fan-out：每列覆蓋一份
            for m in matched:
                clone = _apply_manual_fields(r, m)
                out.append(clone)
        else:
            # 沒有手動列就原樣
            out.append(r)

    # ---- 中文分類（map）----
    for r in out:
        if r.get("category_zh"):
            r["categories_zh"] = [
                x.strip() for x in str(r["category_zh"]).replace("；",";").replace("/", ";").split(";") if x.strip()
            ]
        else:
            en = r.get("categories") or []
            r["categories_zh"] = [catmap.get(x, x) for x in en]

    # ---- 機制中文（map；若無對應就沿用英文）----
    for r in out:
        mechs = r.get("mechanics") or []
        r["mechanics_zh"] = [mechmap.get(x, x) for x in mechs]

    BGG_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"apply_taxonomy_and_price: total {len(out)}; categories_zh & mechanics_zh applied (fan-out enabled).")

if __name__ == "__main__":
    main()

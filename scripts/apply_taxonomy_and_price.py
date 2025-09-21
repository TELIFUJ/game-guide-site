# scripts/apply_taxonomy_and_price.py
import csv, json, math
from pathlib import Path

MANUAL_CSV = Path("data/manual.csv")
BGG_IN     = Path("data/bgg_data.json")
BGG_OUT    = Path("data/bgg_data.json")  # 覆蓋回去
CATMAP_CSV = Path("data/category_map_zh.csv")
MECHMAP_CSV= Path("data/mechanism_map_zh.csv")  # ★ 新增：機制對照
RULES_JSON = Path("data/price_rules.json")

def round_to_step(x, step):
    return int(step * round(float(x)/step))

def to_int_or_none(v):
    if v is None: return None
    s = str(v).strip()
    if s == "" or s.lower() == "none": return None
    try: return int(float(s))
    except: return None

def load_manual():
    items = {}
    if not MANUAL_CSV.exists(): return items
    with MANUAL_CSV.open(encoding="utf-8-sig") as f:  # 容忍 BOM
        r = csv.DictReader(f)
        for row in r:
            key = row.get("bgg_id") or row.get("name_zh") or row.get("bgg_query")
            if not key: continue
            row["manual_override"] = int(row.get("manual_override") or 0)
            row["price_twd"]       = to_int_or_none(row.get("price_twd"))
            row["used_price_twd"]  = to_int_or_none(row.get("used_price_twd"))
            row["price_msrp_twd"]  = to_int_or_none(row.get("price_msrp_twd"))
            row["stock"]           = to_int_or_none(row.get("stock"))
            if row.get("image_version_id") is not None:
                row["image_version_id"] = str(row["image_version_id"]).strip()
            items[str(key)] = row
    return items

def load_catmap():
    m = {}
    if not CATMAP_CSV.exists(): return m
    with CATMAP_CSV.open(encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            en = (row.get("bgg_category_en") or "").strip()
            zh = (row.get("category_zh") or "").strip()
            if en: m[en] = zh or en
    return m

# ★ 新增：讀機制對照
def load_mechmap():
    m = {}
    if not MECHMAP_CSV.exists(): return m
    with MECHMAP_CSV.open(encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            en = (row.get("bgg_mechanism_en") or "").strip()
            zh = (row.get("mechanism_zh") or "").strip()
            if en: m[en] = zh or en
    return m

def match_rule(rule, row):
    cond = rule.get("match", {})
    cz = row.get("categories_zh") or []
    w  = row.get("weight")
    ok = True
    if "category_zh" in cond:
        ok = ok and (cond["category_zh"] in cz)
    if "weight_lte" in cond and w is not None:
        ok = ok and (w <= float(cond["weight_lte"]))
    if "weight_gt" in cond and w is not None:
        ok = ok and (w > float(cond["weight_gt"]))
    return ok

def apply_rules(row, rules, default_used_pct, round_step):
    if row.get("manual_override") == 1:
        return row
    price = row.get("price_twd")
    used  = row.get("used_price_twd")
    for r in rules:
        if not match_rule(r, row): 
            continue
        if "price_set" in r and (price is None):
            price = int(r["price_set"])
        if "used_set" in r:
            used = int(r["used_set"])
        if "used_pct" in r and price is not None:
            used = round_to_step(price * float(r["used_pct"]), round_step)
    if used is None and price is not None:
        used = round_to_step(price * float(default_used_pct), round_step)
    row["price_twd"] = price
    row["used_price_twd"] = used
    return row

def main():
    if not BGG_IN.exists():
        print("No data/bgg_data.json; skip.")
        return

    manual = load_manual()
    catmap = load_catmap()
    mechmap= load_mechmap()  # ★ 新增
    rules_cfg = json.loads(RULES_JSON.read_text(encoding="utf-8")) if RULES_JSON.exists() else {}
    rules = rules_cfg.get("rules", [])
    default_used_pct = rules_cfg.get("default_used_pct", 0.65)
    round_step = rules_cfg.get("round_step", 50)

    rows = json.loads(BGG_IN.read_text(encoding="utf-8"))
    out = []
    changed = 0
    overrides = 0

    for r in rows:
        key = str(r.get("bgg_id") or r.get("name_zh") or r.get("bgg_query"))
        m = manual.get(key) or manual.get(str(r.get("bgg_id"))) or {}

        # 合併手動欄位（擴充）
        if m.get("name_zh"): r["name_zh"] = m["name_zh"]
        if m.get("name_en_override"): r["name_en_override"] = m["name_en_override"]
        if m.get("alias_zh"):
            r["aliases_zh"] = [x.strip() for x in str(m["alias_zh"]).replace("；",";").split(";") if x.strip()]

        if "price_msrp_twd" in m and m["price_msrp_twd"] is not None: r["price_msrp_twd"] = m["price_msrp_twd"]
        if "price_twd"      in m and m["price_twd"]      is not None: r["price_twd"]      = m["price_twd"]
        if "used_price_twd" in m and m["used_price_twd"] is not None: r["used_price_twd"] = m["used_price_twd"]
        if m.get("price_note"): r["price_note"] = m["price_note"]
        if m.get("used_note"):  r["used_note"]  = m["used_note"]
        if m.get("stock") is not None: r["stock"] = m["stock"]
        r["manual_override"] = m.get("manual_override", r.get("manual_override", 0))
        if m.get("description"): r["description"] = m["description"]

        # 圖片／版本圖
        if m.get("image_override"):   r["image_url"] = m["image_override"]
        if m.get("image_version_id"): r["image_version_id"] = m["image_version_id"]

        # 中文分類
        manual_cat = (m.get("category_zh") or "").strip()
        if manual_cat:
            tokens = str(manual_cat).replace("；",";").replace("/", ";").split(";")
            r["categories_zh"] = [x.strip() for x in tokens if x.strip()]
        else:
            en = r.get("categories") or []
            r["categories_zh"] = [catmap.get(x, x) for x in en]

        # ★ 機制中文（全部保留）
        en_mechs = r.get("mechanics") or []
        r["mechanics_zh"] = [(mechmap.get(x) or x) for x in en_mechs]

        before = (r.get("price_twd"), r.get("used_price_twd"))
        r = apply_rules(r, rules, default_used_pct, round_step)
        after  = (r.get("price_twd"), r.get("used_price_twd"))
        if after != before: changed += 1
        if r.get("manual_override") == 1: overrides += 1

        out.append(r)

    BGG_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"apply_taxonomy_and_price: {changed} updated, {overrides} manual-override, total {len(out)}")

if __name__ == "__main__":
    main()

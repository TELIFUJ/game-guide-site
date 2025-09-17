# scripts/apply_taxonomy_and_price.py
import csv, json, math
from pathlib import Path

MANUAL_CSV = Path("data/manual.csv")
BGG_IN     = Path("data/bgg_data.json")
BGG_OUT    = Path("data/bgg_data.json")  # 覆蓋回去
CATMAP_CSV = Path("data/category_map_zh.csv")
RULES_JSON = Path("data/price_rules.json")

def round_to_step(x, step):
    return int(step * round(float(x)/step))

def load_manual():
    items = {}
    if not MANUAL_CSV.exists(): return items
    with MANUAL_CSV.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            key = row.get("bgg_id") or row.get("name_zh") or row.get("bgg_query")
            if not key: continue
            # 正規化
            row["manual_override"] = int(row.get("manual_override") or 0)
            for k in ("price_twd","used_price_twd"):
                v = row.get(k)
                row[k] = int(float(v)) if v not in (None,""," ") else None
            items[str(key)] = row
    return items

def load_catmap():
    m = {}
    if not CATMAP_CSV.exists(): return m
    with CATMAP_CSV.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            en = row.get("bgg_category_en","").strip()
            zh = row.get("category_zh","").strip()
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
    # 若手動覆寫，直接返回
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

    # 若仍無二手價且有售價，走預設折扣
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

        # 1) 合併手動欄位
        r["name_zh"] = m.get("name_zh") or r.get("name_zh")
        r["price_twd"] = m.get("price_twd", r.get("price_twd"))
        r["used_price_twd"] = m.get("used_price_twd", r.get("used_price_twd"))
        r["stock"] = m.get("stock", r.get("stock"))
        r["manual_override"] = m.get("manual_override", 0)

        # 2) 中文分類：manual.category_zh 優先，其次用對照表把 BGG 英文分類轉中文
        manual_cat = (m.get("category_zh") or "").strip()
        if manual_cat:
            r["categories_zh"] = [x.strip() for x in manual_cat.split("/") if x.strip()]
        else:
            en = r.get("categories") or []
            r["categories_zh"] = [catmap.get(x, x) for x in en]

        # 3) 套用價格規則（若 manual_override=1 不改）
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

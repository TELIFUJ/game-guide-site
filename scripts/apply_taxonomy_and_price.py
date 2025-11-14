# scripts/apply_taxonomy_and_price.py
import json, csv, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INP  = DATA / "bgg_data.json"
OUT  = DATA / "bgg_data.json"   # 覆寫回去

MECH_CSV = DATA / "mechanism_map_zh.csv"
CATE_CSV = DATA / "category_map_zh.csv"
MANUAL_CSV = DATA / "manual.csv"
PRICE_RULES = DATA / "price_rules.json"

def load_map(path, en_keys, zh_keys):
    if not path.exists(): return {}
    with path.open(encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        res = {}
        for r in rdr:
            en = None; zh = None
            for k in en_keys:
                if k in r and r[k]:
                    en = r[k].strip()
                    break
            for k in zh_keys:
                if k in r and r[k]:
                    zh = r[k].strip()
                    break
            if en:
                res[en.lower()] = zh or en
        return res

def load_manual():
    m = {}
    if not MANUAL_CSV.exists(): return m
    with MANUAL_CSV.open(encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            try:
                bid = int(str(r.get("bgg_id") or r.get("id") or "").strip())
            except:
                continue
            m[bid] = {
                "name_zh": r.get("name_zh") or r.get("zh"),
                "image_override": r.get("image_override") or r.get("image"),
                "price": r.get("price"),
                "price_used": r.get("price_used") or r.get("price_second"),
            }
    return m

def load_price_rules():
    if PRICE_RULES.exists():
        try:
            return json.loads(PRICE_RULES.read_text(encoding="utf-8"))
        except:
            return {}
    return {}

mech_map = load_map(MECH_CSV, ["bgg_mechanism_en","mechanism_en","mechanism"], ["mechanism_zh","zh"])
cate_map = load_map(CATE_CSV, ["bgg_category_en","category_en","category"], ["category_zh","zh"])
manual = load_manual()
price_rules = load_price_rules()

rows = json.loads(INP.read_text(encoding="utf-8")) if INP.exists() else []
out = []
tax_count = 0; price_count = 0; override_count = 0

for r in rows:
    if not isinstance(r, dict): 
        continue
    bid = int(r.get("bgg_id") or r.get("id") or 0)

    # 備份英文 → 轉中文（若有對照表）
    cats_en = list(r.get("categories") or [])
    mechs_en = list(r.get("mechanisms") or [])
    r["categories_en"] = cats_en
    r["mechanisms_en"] = mechs_en
    cats_zh = [(cate_map.get(c.lower(), c) if isinstance(c,str) else c) for c in cats_en]
    mechs_zh = [(mech_map.get(m.lower(), m) if isinstance(m,str) else m) for m in mechs_en]
    if cats_zh != cats_en or mechs_zh != mechs_en:
        tax_count += 1
    # 直接覆蓋主欄位，前端無需修改即可顯示中文
    r["categories"] = cats_zh
    r["mechanisms"] = mechs_zh

    # 手動覆寫
    if bid in manual:
        m = manual[bid]
        if m.get("name_zh"): r["name_zh"] = m["name_zh"]
        if m.get("image_override"): r["image_override"] = m["image_override"]
        if m.get("price"): r["price"] = m["price"]
        if m.get("price_used"): r["price_used"] = m["price_used"]
        override_count += 1

    # 規則價（若有）
    if price_rules:
        p = price_rules.get(str(bid)) or price_rules.get(bid)
        if isinstance(p, dict):
            r.update(p); price_count += 1

    out.append(r)

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Merged taxonomy({tax_count}) price({price_count}) overrides({override_count}) → total {len(out)} → {OUT}")

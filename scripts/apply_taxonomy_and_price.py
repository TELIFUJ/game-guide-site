import csv, json, urllib.parse
from pathlib import Path

BGG_IN      = Path("data/bgg_data.json")
CATMAP_CSV  = Path("data/category_map_zh.csv")
MECHMAP_CSV = Path("data/mechanism_map_zh.csv")

def load_map(csv_path, key_en, key_zh):
    m = {}
    if not csv_path.exists(): return m
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            en = (row.get(key_en) or "").strip()
            zh = (row.get(key_zh) or "").strip()
            if en:
                m[en] = zh or en
    return m

def parse_list_zh(s: str):
    return [x.strip() for x in str(s).replace("；",";").replace("/", ";").split(";") if x.strip()]

def with_cache_param(url: str, ver: str|None):
    if not url or not ver: return url
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qsl(u.query, keep_blank_values=True)
    if any(k.lower()=="v" for k,_ in q):
        return url
    q.append(("v", str(ver)))
    new_q = urllib.parse.urlencode(q)
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, new_q, u.fragment))

def main():
    if not BGG_IN.exists():
        print("No data/bgg_data.json; skip apply."); return

    catmap  = load_map(CATMAP_CSV,  "bgg_category_en",  "category_zh")
    mechmap = load_map(MECHMAP_CSV, "bgg_mechanism_en", "mechanism_zh")

    rows = json.loads(BGG_IN.read_text(encoding="utf-8"))
    out  = []

    for r in rows:
        rr = dict(r)

        # alias_zh -> aliases_zh 陣列
        if rr.get("alias_zh"):
            rr["aliases_zh"] = [x.strip() for x in str(rr["alias_zh"]).split(";") if x.strip()]

        # 只要有 image_override 就直接定案到 image，並加 v= 抗快取
        img_ovr = (rr.get("image_override") or "").strip()
        if img_ovr:
            ver = (str(rr.get("image_version_id")).strip()
                   if rr.get("image_version_id") not in (None, "") else None)
            rr["image"] = with_cache_param(img_ovr, ver)

        # 分類中文
        if rr.get("category_zh"):
            rr["categories_zh"] = parse_list_zh(rr["category_zh"])
        else:
            en = rr.get("categories") or []
            rr["categories_zh"] = [catmap.get(x, x) for x in en]

        # 機制中文
        mechs = rr.get("mechanics") or []
        rr["mechanics_zh"] = [mechmap.get(x, x) for x in mechs]

        out.append(rr)

    BGG_IN.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"apply_taxonomy_and_price: total {len(out)}; categories_zh & mechanics_zh applied (no fan-out).")

if __name__ == "__main__":
    main()

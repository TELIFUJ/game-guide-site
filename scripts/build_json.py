# scripts/build_json.py
import json, datetime, hashlib, urllib.parse
from pathlib import Path

INPUT=Path("data/bgg_data.json")
OUTPUT=Path("data/games_full.json")

def slugify(s:str)->str:
    return (s or "").strip().lower().replace(" ","_")

def with_cache_param(url:str, ver:str|None)->str:
    if not url or not ver: return url
    # 如果已經存在 v= 參數，就不重複加
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qsl(u.query, keep_blank_values=True)
    if any(k.lower()=="v" for k,_ in q):
        return url
    q.append(("v", str(ver)))
    new_q = urllib.parse.urlencode(q)
    return urllib.parse.urlunsplit((u.scheme,u.netloc,u.path,new_q,u.fragment))

if not INPUT.exists():
    print("No data/bgg_data.json; skip build_json."); raise SystemExit(0)

rows=json.loads(INPUT.read_text(encoding="utf-8"))
items=[]; today=datetime.date.today().isoformat()

for r in rows:
    bid=r.get("bgg_id")
    name_zh=r.get("name_zh")
    name_en=r.get("name_en_override") or r.get("name_en") or r.get("bgg_query")
    edition_key = r.get("edition_key")  # 可能是 None

    # 圖片：CSV override 永遠第一，並帶上版本參數
    image = r.get("image_override") or r.get("image") or r.get("image_url") or r.get("thumb_url")
    image = with_cache_param(image, r.get("image_version_id"))

    # 生成穩定 id（避免被合併）
    base = slugify(name_en or name_zh or (f"bgg_{bid}" if bid else "game"))
    if edition_key:  # 首選：edition 複合鍵
        item_id = f"{bid}#ed:{slugify(edition_key)}" if bid else f"{base}#ed:{slugify(edition_key)}"
    elif r.get("image_override"):  # 次選：覆蓋圖的短雜湊
        suffix = hashlib.md5(r["image_override"].encode("utf-8")).hexdigest()[:8]
        item_id = f"{base}-{suffix}"
    elif bid:
        item_id = f"{base}-{bid}"
    else:
        item_id = base

    search_keywords = r.get("search_keywords") or []
    if not search_keywords:
        if name_zh: search_keywords.append(f"{name_zh} BGG")
        if name_en: search_keywords.append(f"{name_en} BGG")

    items.append({
        "id": item_id,
        "is_variant_of": r.get("is_variant_of"),   # 供前端聚合用（選擇性）
        "edition_key": edition_key,
        "name_zh": name_zh,
        "name_en": name_en,
        "aliases_zh": r.get("aliases_zh", []),
        "bgg_id": bid,
        "bgg_url": r.get("bgg_url") or (f"https://boardgamegeek.com/boardgame/{bid}" if bid else None),
        "year": r.get("year"),
        "players": r.get("players"),
        "time_min": r.get("time_min"),
        "time_max": r.get("time_max"),
        "weight": r.get("weight"),
        "categories": r.get("categories") or [],
        "categories_zh": r.get("categories_zh") or [],
        "mechanics": r.get("mechanics") or [],
        "mechanics_zh": r.get("mechanics_zh") or [],
        "versions_count": r.get("versions_count", 0),
        "image": image,
        "price_msrp_twd": r.get("price_msrp_twd"),
        "price_twd": r.get("price_twd"),
        "used_price_twd": r.get("used_price_twd"),
        "price_note": r.get("price_note"),
        "used_note": r.get("used_note"),
        "stock": r.get("stock"),
        "description": r.get("description"),
        "search_keywords": search_keywords,
        "updated_at": today
    })

# 穩定輸出
items.sort(key=lambda x: (x.get("name_zh") or x.get("name_en") or "").lower())

OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Built {len(items)} entries → {OUTPUT}")

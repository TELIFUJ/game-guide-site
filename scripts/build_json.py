import json, datetime
from pathlib import Path

INPUT=Path("data/bgg_data.json")
OUTPUT=Path("data/games_full.json")

def slugify(s:str)->str:
    return (s or "").strip().lower().replace(" ","_")

if not INPUT.exists():
    print("No data/bgg_data.json; skip build_json."); raise SystemExit(0)

rows=json.loads(INPUT.read_text(encoding="utf-8"))
items=[]; today=datetime.date.today().isoformat()

# 追蹤已使用的 id，確保唯一
seen={}
def unique_id(base:str)->str:
    c = seen.get(base, 0)
    if c==0:
        seen[base]=1
        return base
    else:
        c+=1
        seen[base]=c
        return f"{base}-{c}"

for r in rows:
    bid=r.get("bgg_id")
    bgg_url=f"https://boardgamegeek.com/boardgame/{bid}" if bid else None
    name_zh=r.get("name_zh")
    name_en=r.get("name_en_override") or r.get("name_en") or r.get("bgg_query")

    # 基礎 slug
    base = slugify(name_en or name_zh or (f"bgg_{bid}" if bid else "game"))

    # 若這筆有版本資訊，優先以版本做識別（避免兩筆撞名）
    ver = r.get("image_version_used") or r.get("image_version_id")
    if ver:
        base = f"{base}-v{ver}"

    uid = unique_id(base)

    image=r.get("image") or r.get("image_url") or r.get("thumb_url")
    if r.get("image_override"): image = r["image_override"]

    search_keywords=[]
    if name_zh: search_keywords.append(f"{name_zh} BGG")
    if name_en: search_keywords.append(f"{name_en} BGG")

    items.append({
      "id": uid,
      "name_zh": name_zh, "name_en": name_en, "aliases_zh": r.get("aliases_zh", []),
      "bgg_id": bid, "bgg_url": bgg_url, "year": r.get("year"), "players": r.get("players"),
      "time_min": r.get("time_min"), "time_max": r.get("time_max"), "weight": r.get("weight"),
      "categories": r.get("categories") or [], "categories_zh": r.get("categories_zh") or [],
      "mechanics": r.get("mechanics") or [], "mechanics_zh": r.get("mechanics_zh") or [],
      "versions_count": r.get("versions_count", 0),
      "image": image, "price_msrp_twd": r.get("price_msrp_twd"), "price_twd": r.get("price_twd"),
      "used_price_twd": r.get("used_price_twd"), "price_note": r.get("price_note"),
      "used_note": r.get("used_note"), "stock": r.get("stock"), "description": r.get("description"),
      # 外部連結（自有頁面）可選；有的話前端會改顯示「介紹」
      "external_url": r.get("external_url"),
      "image_version_used": r.get("image_version_used"),
      "image_version_id": r.get("image_version_id"),
      "search_keywords": search_keywords, "updated_at": today
    })

OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Built {len(items)} entries → {OUTPUT}")

# scripts/build_json.py
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

for r in rows:
    bid=r.get("bgg_id")
    bgg_url=f"https://boardgamegeek.com/boardgame/{bid}" if bid else None
    name_zh=r.get("name_zh")
    name_en=r.get("name_en_override") or r.get("name_en") or r.get("bgg_query")

    # 圖片：**永遠以 image_override 優先**；否則回退到 image / image_url / thumb_url
    image = r.get("image_override") or r.get("image") or r.get("image_url") or r.get("thumb_url")

    search_keywords=[]
    if name_zh: search_keywords.append(f"{name_zh} BGG")
    if name_en: search_keywords.append(f"{name_en} BGG")

    items.append({
        "id": (name_en or name_zh or f"bgg_{bid}").lower().replace(" ","_") if (name_en or name_zh) else f"bgg_{bid}",
        "name_zh": name_zh, "name_en": name_en, "aliases_zh": r.get("aliases_zh", []),
        "bgg_id": bid, "bgg_url": r.get("bgg_url") or bgg_url,
        "year": r.get("year"), "players": r.get("players"),
        "time_min": r.get("time_min"), "time_max": r.get("time_max"), "weight": r.get("weight"),
        "categories": r.get("categories") or [], "categories_zh": r.get("categories_zh") or [],
        "mechanics": r.get("mechanics") or [], "mechanics_zh": r.get("mechanics_zh") or [],
        "versions_count": r.get("versions_count", 0),
        "image": image,
        "price_msrp_twd": r.get("price_msrp_twd"), "price_twd": r.get("price_twd"),
        "used_price_twd": r.get("used_price_twd"), "price_note": r.get("price_note"),
        "used_note": r.get("used_note"), "stock": r.get("stock"), "description": r.get("description"),
        "search_keywords": r.get("search_keywords") or search_keywords,
        "updated_at": today
    })

OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Built {len(items)} entries → {OUTPUT}")

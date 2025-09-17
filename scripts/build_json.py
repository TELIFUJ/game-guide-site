# scripts/build_json.py
import json, datetime
from pathlib import Path

INPUT = Path("data/bgg_data.json")
OUTPUT = Path("data/games_full.json")

if not INPUT.exists():
    print("No data/bgg_data.json; skip build_json.")
    raise SystemExit(0)

rows = json.loads(INPUT.read_text(encoding="utf-8"))
items = []
today = datetime.date.today().isoformat()

for r in rows:
    bid = r.get("bgg_id")
    bgg_url = f"https://boardgamegeek.com/boardgame/{bid}" if bid else None
    name_zh = r.get("name_zh")
    name_en = r.get("name_en") or r.get("bgg_query")
    categories = r.get("categories") or []
    mechanics  = r.get("mechanics") or []
    # 產生搜尋關鍵字（台灣常用）
    search_keywords = []
    if name_zh: search_keywords.append(f"{name_zh} BGG")
    if name_en: search_keywords.append(f"{name_en} BGG")

    items.append({
        "id": (name_en or name_zh or f"bgg_{bid}").lower().replace(" ", "_"),
        "name_zh": name_zh,
        "name_en": name_en,
        "aliases_zh": [],  # 後續可由 CSV 增加
        "bgg_id": bid,
        "bgg_url": bgg_url,
        "year": r.get("year"),
        "players": r.get("players"),
        "time_min": r.get("time_min"),
        "time_max": r.get("time_max"),
        "weight": r.get("weight"),
        "categories": categories,
        "mechanics": mechanics,
        "editions": [],  # 之後可補
        "image": r.get("image") or r.get("image_url") or r.get("thumb_url"),
        "price_twd": r.get("price_twd"),
        "used_price_twd": r.get("used_price_twd"),
        "price_usd_amz": None,
        "search_keywords": search_keywords,
        "stock": r.get("stock"),
        "updated_at": today
    })

OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Built {len(items)} entries → {OUTPUT}")

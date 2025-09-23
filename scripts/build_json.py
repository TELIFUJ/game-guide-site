# scripts/build_json.py
import json, datetime
from pathlib import Path

INPUT  = Path("data/bgg_data.json")
OUTPUT = Path("data/games_full.json")

def slugify(s:str)->str:
    return (s or "").strip().lower().replace(" ","_")

if not INPUT.exists():
    print("No data/bgg_data.json; skip build_json."); raise SystemExit(0)

rows  = json.loads(INPUT.read_text(encoding="utf-8"))
items = []
today = datetime.date.today().isoformat()

for r in rows:
    bid     = r.get("bgg_id")
    bgg_url = f"https://boardgamegeek.com/boardgame/{bid}" if bid else None

    # 名稱（維持你以前的規則）
    name_zh = r.get("name_zh")
    name_en = r.get("name_en_override") or r.get("name_en") or r.get("bgg_query")

    # 圖片（重點：CSV 的 image_override 優先）
    image = r.get("image") or r.get("image_url") or r.get("thumb_url")
    if r.get("image_override"):
        image = r["image_override"]   # 還原成你之前的做法：一定吃 CSV 連結

    # 搜尋關鍵字
    search_keywords=[]
    if name_zh: search_keywords.append(f"{name_zh} BGG")
    if name_en: search_keywords.append(f"{name_en} BGG")

    # id（維持舊規則；不同 name_zh/EN 會變不同 id）
    if (name_en or name_zh):
        item_id = slugify(name_en or name_zh)
    else:
        item_id = f"bgg_{bid}"

    items.append({
      "id": item_id,
      "name_zh": name_zh,
      "name_en": name_en,
      "aliases_zh": r.get("aliases_zh", []),

      "bgg_id": bid,
      "bgg_url": bgg_url,

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

      "image": image,   # ← 關鍵：用上面決定好的 image（CSV 會蓋過）
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

OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Built {len(items)} entries → {OUTPUT}")

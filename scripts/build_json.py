# scripts/build_json.py
import json, os

INPUT = "data/bgg_data.json"
OUTPUT = "data/games_full.json"

if not os.path.exists(INPUT):
    print("No input file found. Please run previous scripts first.")
    exit(1)

with open(INPUT, encoding="utf-8") as f:
    data = json.load(f)

# 最終輸出格式：只保留必要欄位
output = []
for row in data:
    output.append({
        "name_zh": row.get("name_zh"),
        "name_en": row.get("bgg_query"),
        "bgg_id": row.get("bgg_id"),
        "bgg_url": f"https://boardgamegeek.com/boardgame/{row['bgg_id']}",
        "year": row.get("year"),
        "weight": row.get("weight"),
        "categories": row.get("categories"),
        "image": row.get("image"),
        "price_twd": row.get("price_twd"),
        "used_price_twd": row.get("used_price_twd")
    })

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Built {len(output)} entries → {OUTPUT}")

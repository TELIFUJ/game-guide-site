# scripts/fetch_bgg.py
import json, os

INPUT = "data/bgg_ids.json"
OUTPUT = "data/bgg_data.json"

if not os.path.exists(INPUT):
    print("No input file found. Please run resolve_bgg.py first.")
    exit(1)

with open(INPUT, encoding="utf-8") as f:
    rows = json.load(f)

# Demo: 加上假資料欄位（實際上未來會用 BGG API）
for row in rows:
    row["year"] = 2014 if row["bgg_id"] == 148228 else 2010
    row["weight"] = 1.8 if row["bgg_id"] == 148228 else 2.3
    row["categories"] = ["Card Game","Economic"] if row["bgg_id"] == 148228 else ["Card Game","Civilization"]
    row["image"] = f"https://via.placeholder.com/300x160?text={row['name_zh']}"

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)

print(f"Fetched {len(rows)} entries → {OUTPUT}")

# scripts/resolve_bgg.py
import os, json

os.makedirs("data", exist_ok=True)

# 建立一個測試資料
rows = [
    {"name_zh": "璀璨寶石", "bgg_query": "Splendor", "price_twd": 1200, "used_price_twd": 800, "bgg_id": 148228},
    {"name_zh": "七大奇蹟", "bgg_query": "7 Wonders", "price_twd": 1900, "used_price_twd": 1200, "bgg_id": 68448}
]

with open("data/bgg_ids.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)

print(f"Resolved {len(rows)} entries → data/bgg_ids.json")

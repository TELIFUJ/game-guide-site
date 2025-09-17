# scripts/download_images.py
import os, requests, json

INPUT = "data/bgg_data.json"
IMG_DIR = "assets/img"
os.makedirs(IMG_DIR, exist_ok=True)

if not os.path.exists(INPUT):
    print("No input file found. Please run fetch_bgg.py first.")
    exit(1)

with open(INPUT, encoding="utf-8") as f:
    rows = json.load(f)

for row in rows:
    url = row.get("image")
    if not url:
        continue
    filename = f"{row['bgg_id']}.jpg"
    path = os.path.join(IMG_DIR, filename)
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:

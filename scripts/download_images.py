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
            with open(path, "wb") as f:
                f.write(r.content)
            row["image"] = f"assets/img/{filename}"
            print(f"Downloaded {row['name_zh']} → {path}")
    except Exception as e:
        print(f"Failed {row['name_zh']}: {e}")

# 覆蓋回去，讓下一步 build_json.py 用到更新過的 image 路徑
with open(INPUT, "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)


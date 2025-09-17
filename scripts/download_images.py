# scripts/download_images.py
import os, json, requests, time
from pathlib import Path
from PIL import Image
from io import BytesIO

INPUT = Path("data/bgg_data.json")
IMG_DIR = Path("assets/img")
IMG_DIR.mkdir(parents=True, exist_ok=True)

if not INPUT.exists():
    print("No data/bgg_data.json; skip download_images.")
    raise SystemExit(0)

rows = json.loads(INPUT.read_text(encoding="utf-8"))
updated = []

def save_thumb(content: bytes, dest: Path):
    img = Image.open(BytesIO(content))
    img.thumbnail((300, 300))
    img.convert("RGB").save(dest, "JPEG", quality=82, optimize=True)

for r in rows:
    bid = r.get("bgg_id")
    url = r.get("image_url") or r.get("thumb_url")
    if not bid or not url:
        updated.append(r)
        continue
    dest = IMG_DIR / f"{bid}.jpg"
    if dest.exists():
        # 已有縮圖 → 確保 image 指向本地檔
        r["image"] = f"assets/img/{bid}.jpg"
        updated.append(r)
        continue
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        save_thumb(resp.content, dest)
        r["image"] = f"assets/img/{bid}.jpg"
        print(f"Downloaded {r.get('name_zh') or r.get('name_en')} → {dest}")
        time.sleep(0.7)
    except Exception as e:
        # 下載失敗：保留遠端網址，前端依然能顯示
        r["image"] = url
        print(f"Image fallback {bid}: {e}")
    updated.append(r)

INPUT.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
print("download_images: done.")

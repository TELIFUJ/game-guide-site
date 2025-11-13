# scripts/download_images.py
# -*- coding: utf-8 -*-
import json, requests, hashlib, time
from pathlib import Path
from PIL import Image
from io import BytesIO

INPUT  = Path("data/bgg_data.json")
IMG_DIR = Path("site/assets/img")
IMG_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "GameGuide Image Fetcher/1.0 (+https://github.com/TELIFUJ/game-guide-site)",
    "Referer": "https://boardgamegeek.com/",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}

def save_thumb(content: bytes, dest: Path):
    img = Image.open(BytesIO(content))
    img.thumbnail((300, 300))  # 如需更清晰可改 512
    img.convert("RGB").save(dest, "JPEG", quality=82, optimize=True)

def main():
    if not INPUT.exists():
        print("No data/bgg_data.json; skip download_images.")
        return

    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    updated = []

    for r in rows:
        # 1) CSV 指定 override → 完全尊重，不下載
        if r.get("image_override"):
            ver = (str(r.get("image_version_id")).strip()
                   if r.get("image_version_id") not in (None, "") else None)
            r["image"] = r.get("image") or r["image_override"]
            if r["image"] and ver:
                r["image"] = f"{r['image']}{'&' if '?' in r['image'] else '?'}v={ver}"
            updated.append(r)
            continue

        # 2) 從多種欄位取圖（相容兩種抓取器）
        url = (
            r.get("image_url")
            or r.get("thumb_url")
            or r.get("image")
            or r.get("thumbnail")
        )
        if not url:
            updated.append(r)
            continue

        # 3) 以 URL 雜湊命名，避免覆蓋
        bid = r.get("bgg_id") or r.get("id") or "noid"
        h = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
        dest = IMG_DIR / f"{bid}-{h}.jpg"

        try:
            if not dest.exists():
                resp = requests.get(url, timeout=60, headers=HEADERS)
                resp.raise_for_status()
                save_thumb(resp.content, dest)
                time.sleep(0.6)  # 節流
            r["image"] = f"assets/img/{dest.name}"
        except Exception as e:
            # 下載失敗就保留原網址，前端仍可顯示
            r["image"] = url
            print(f"Image fallback for {bid}: {e}")

        updated.append(r)

    INPUT.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    print("download_images: done.")

if __name__ == "__main__":
    main()

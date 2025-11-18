#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_images.py — 下載 BGG 圖片到 site/assets/img

規格：
- 讀取 data/bgg_data.json
- 對每一筆：
    * 取 image_url 或 image 或 thumbnail
    * 整理成穩定 HTTPS 原圖網址
    * 用 URL 做 md5 前 8 碼當檔名：{bgg_id}-{hash}{ext}
- 實體檔案寫入 site/assets/img
  → 前端只要用 "assets/img/..." 就能讀到
"""

import hashlib
import json
import pathlib
import requests

from common_image import normalize_bgg_image_url  # 同目錄的 common_image.py

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "bgg_data.json"
OUT = ROOT / "site" / "assets" / "img"
OUT.mkdir(parents=True, exist_ok=True)


def hash_url(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:8]


def main():
    if not DATA.exists():
        raise SystemExit(f"[ERR] 找不到 {DATA}")

    rows = json.loads(DATA.read_text("utf-8"))
    downloaded = 0

    for r in rows:
        bid = r.get("bgg_id")
        if not bid:
            continue

        raw_url = r.get("image_url") or r.get("image") or r.get("thumbnail")
        if not raw_url:
            continue

        url = normalize_bgg_image_url(raw_url)
        if not url:
            continue

        ext = pathlib.Path(url).suffix or ".jpg"
        fname = f"{bid}-{hash_url(url)}{ext}"
        path = OUT / fname

        if path.exists():
            continue

        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200 and resp.content:
                path.write_bytes(resp.content)
                downloaded += 1
                print(f"[OK] saved {fname}")
            else:
                print(f"[WARN] HTTP {resp.status_code} for {bid} → {url}")
        except Exception as e:
            print(f"[ERR] download fail {bid} → {url} ; {e}")

    print(f"download_images: 新下載 {downloaded} 張圖；輸出目錄：{OUT}")


if __name__ == "__main__":
    main()

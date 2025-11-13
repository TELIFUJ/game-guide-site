# -*- coding: utf-8 -*-
"""
下載遊戲圖片到 site/assets/img。
僅對 http/https 來源進行下載；若候選欄位是本地相對路徑（assets/img/...），視為已處理，絕不嘗試 requests.get()。
"""

from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from io import BytesIO
from urllib.parse import urlparse

import requests
from PIL import Image

INPUT   = Path("data/bgg_data.json")
IMG_DIR = Path("site/assets/img")
IMG_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "GameGuide Image Fetcher/1.0 (+https://github.com/TELIFUJ/game-guide-site)",
    "Referer": "https://boardgamegeek.com/",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}

SLEEP = float("0.6")   # 節流
RETRY = 3              # 下載重試次數（輕量即可）


# ---------- helpers ----------

def is_http_url(u: str | None) -> bool:
    if not u or not isinstance(u, str):
        return False
    try:
        p = urlparse(u)
        return p.scheme in ("http", "https")
    except Exception:
        return False


def save_thumb(content: bytes, dest: Path):
    img = Image.open(BytesIO(content))
    img.thumbnail((300, 300))  # 需要更清晰可改 512
    img.convert("RGB").save(dest, "JPEG", quality=82, optimize=True)


def first_http(*candidates: str | None) -> str | None:
    """從多個欄位中，回傳第一個 http(s) 連結；忽略相對路徑（如 assets/img/...）。"""
    for u in candidates:
        if is_http_url(u):
            return u
    return None


# ---------- main ----------

def main():
    if not INPUT.exists():
        print("No data/bgg_data.json; skip download_images.")
        return

    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    updated = []

    for r in rows:
        # 1) CSV 指定 override → 完全尊重（不下載）
        if r.get("image_override"):
            ver = (str(r.get("image_version_id")).strip()
                   if r.get("image_version_id") not in (None, "") else None)
            r["image"] = r.get("image") or r["image_override"]
            if ver and is_http_url(r["image"]):
                r["image"] = f"{r['image']}{'&' if '?' in r['image'] else '?'}v={ver}"
            updated.append(r)
            continue

        # 2) 僅從可用的 http(s) 欄位擇一；忽略本地相對路徑
        url = first_http(
            r.get("image_url"),
            r.get("thumb_url"),
            r.get("image"),      # 若上輪已寫相對路徑，這裡會自動略過
            r.get("thumbnail"),
        )

        # 沒有任何可下載的 http(s) 來源 → 保留原狀
        if not url:
            updated.append(r)
            continue

        # 3) 以 URL 雜湊命名，避免覆蓋
        bid = r.get("bgg_id") or r.get("id") or "noid"
        h = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
        dest = IMG_DIR / f"{bid}-{h}.jpg"

        # 已存在即跳過
        if dest.exists():
            r["image"] = f"assets/img/{dest.name}"
            updated.append(r)
            continue

        last_err = None
        for k in range(RETRY):
            try:
                resp = requests.get(url, timeout=60, headers=HEADERS)
                resp.raise_for_status()
                save_thumb(resp.content, dest)
                r["image"] = f"assets/img/{dest.name}"
                break
            except Exception as e:
                last_err = str(e)
                time.sleep(SLEEP * (1.6 ** k))
        else:
            # 下載失敗：保留原網址，前端仍可顯示；不寫入相對路徑，避免下次誤抓
            r["image"] = url
            print(f"Image fallback for {bid}: {last_err}")

        updated.append(r)

    INPUT.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    print("download_images: done.")


if __name__ == "__main__":
    main()

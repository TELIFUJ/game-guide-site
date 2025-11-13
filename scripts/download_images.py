# scripts/download_images.py
# -*- coding: utf-8 -*-
import json, requests, hashlib, time, re
from pathlib import Path
from PIL import Image
from io import BytesIO

INPUT   = Path("data/bgg_data.json")
IMG_DIR = Path("site/assets/img")
IMG_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "GameGuide Image Fetcher/1.0 (+https://github.com/TELIFUJ/game-guide-site)",
    "Referer": "https://boardgamegeek.com/",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}

HTTP_RE = re.compile(r"^https?://", re.I)

def _is_local_path(u: str) -> bool:
    if not u: return False
    u = u.strip()
    return not HTTP_RE.match(u)

def _localize_path(name: str) -> str:
    # 供前端使用的相對路徑（index.html 位於 site/ 底下）
    return f"assets/img/{name}"

def save_thumb(content: bytes, dest: Path):
    img = Image.open(BytesIO(content))
    img.thumbnail((512, 512))
    img.convert("RGB").save(dest, "JPEG", quality=82, optimize=True)

def main():
    if not INPUT.exists():
        print("No data/bgg_data.json; skip download_images.")
        return

    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    updated = []

    for r in rows:
        # override：尊重使用者指定（不下載）
        if r.get("image_override"):
            url = str(r.get("image_override"))
            ver = (str(r.get("image_version_id")).strip()
                   if r.get("image_version_id") not in (None, "") else None)
            if ver:
                sep = "&" if "?" in url else "?"
                url = f"{url}{sep}v={ver}"
            r["image"] = url
            updated.append(r)
            continue

        # 取圖來源（兼容 bgg 抓取器欄位）
        url = (
            r.get("image_url")
            or r.get("thumb_url")
            or r.get("image")
            or r.get("thumbnail")
        )

        if not url:
            updated.append(r)
            continue

        bid = r.get("bgg_id") or r.get("id") or "noid"
        # 若既是本地相對路徑，不下載，直接寫回
        if _is_local_path(url):
            # 可能是 "site/assets/img/xxx.jpg" 或 "assets/img/xxx.jpg"
            name = Path(url).name
            r["image"] = _localize_path(name)
            updated.append(r)
            continue

        # 遠端 URL：下載並以 URL 雜湊命名，避免覆蓋
        h = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
        dest = IMG_DIR / f"{bid}-{h}.jpg"

        try:
            if not dest.exists():
                resp = requests.get(url, timeout=60, headers=HEADERS)
                resp.raise_for_status()
                save_thumb(resp.content, dest)
                time.sleep(0.6)  # 節流
            r["image"] = _localize_path(dest.name)
        except Exception as e:
            # 下載失敗就保留原網址，前端仍可顯示
            r["image"] = url
            print(f"Image fallback for {bid}: {e}")

        updated.append(r)

    INPUT.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    print("download_images: done.")

if __name__ == "__main__":
    main()

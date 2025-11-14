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
    "User-Agent": "GameGuide Image Fetcher/1.0 (+https://g#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
將所有圖片統一下載/整理至 assets/img/；嚴格尊重 image_override；
檔名規則：
  - 若有 image_override：完全尊重其相對路徑（若未含 assets/ 前綴則補上 assets/img/）。
  - 否則以 BGG id 命名：{id}.ext（從 URL 或 Content-Type 猜測；預設 .jpg）。
此檔不直接改寫 JSON，僅負責檔案落地；由 build_json.py 決定最終使用路徑。
"""
import pathlib, json, re, sys, os
from urllib.parse import urlparse
import mimetypes

try:
    import requests
except Exception:
    print("[download_images] requests 未安裝，跳過下載。", file=sys.stderr)
    sys.exit(0)

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_IN = ROOT / "data" / "bgg_data.json"
IMG_DIR = ROOT / "assets" / "img"
IMG_DIR.mkdir(parents=True, exist_ok=True)

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
SESS = requests.Session()
SESS.headers.update({"User-Agent": "BGG-Guide-ImageFetcher/1.2"})

def safe_ext_from_url(url: str) -> str:
    try:
        path = urlparse(url).path
        ext = pathlib.Path(path).suffix.lower()
        if ext in IMG_EXTS:
            return ext
    except Exception:
        pass
    return ""

def guess_ext_from_head(url: str) -> str:
    try:
        r = SESS.head(url, timeout=15, allow_redirects=True)
        ct = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
        ext = mimetypes.guess_extension(ct) or ""
        if ext.lower() in IMG_EXTS:
            return ext.lower()
    except Exception:
        return ""
    return ""

def ensure_override_path(override: str) -> pathlib.Path:
    p = pathlib.Path(override)
    if not (str(p).startswith("assets/") or str(p).startswith("./assets/")):
        p = pathlib.Path("assets") / "img" / p
    full = ROOT / p
    full.parent.mkdir(parents=True, exist_ok=True)
    return full

def download(url: str, dest: pathlib.Path):
    if dest.exists() and dest.stat().st_size > 0:
        return
    try:
        with SESS.get(url, timeout=60, stream=True) as r:
            r.raise_for_status()
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            tmp.replace(dest)
    except Exception as e:
        print(f"[download_images] 下載失敗 {url} → {dest}: {e}", file=sys.stderr)

def main():
    if not DATA_IN.exists():
        print(f"[download_images] 找不到 {DATA_IN}", file=sys.stderr)
        return

    data = json.loads(DATA_IN.read_text(encoding="utf-8"))
    n_total, n_ok = 0, 0

    for r in data:
        n_total += 1
        gid = str(r.get("id") or r.get("game_id") or "").strip()
        override = (r.get("image_override") or "").strip()
        image_url = (r.get("image_url") or r.get("image") or "").strip()

        # 優先尊重 override：僅確保路徑存在，不下載
        if override:
            dst = ensure_override_path(override)
            # 若 override 指向現有檔案就算成功；否則留給前端 fallback
            if dst.exists() and dst.stat().st_size > 0:
                n_ok += 1
            continue

        # 無 override，以 id 命名
        if not gid:
            continue
        ext = safe_ext_from_url(image_url) if image_url else ""
        if not ext:
            ext = guess_ext_from_head(image_url) if image_url else ""
        if not ext:
            ext = ".jpg"
        dst = IMG_DIR / f"{gid}{ext}"
        if image_url:
            download(image_url, dst)
            if dst.exists() and dst.stat().st_size > 0:
                n_ok += 1

    print(f"download_images: {n_ok}/{n_total} ready at {IMG_DIR}")

if __name__ == "__main__":
    main()
ithub.com/TELIFUJ/game-guide-site)",
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

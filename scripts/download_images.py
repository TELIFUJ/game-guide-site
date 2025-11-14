#!/usr/bin/env python3
import json, pathlib, requests, hashlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "bgg_data.json"
OUT = ROOT / "assets" / "img"
OUT.mkdir(parents=True, exist_ok=True)

def hash_url(url):
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:8]

def main():
    rows = json.loads(DATA.read_text("utf-8"))
    for r in rows:
        bid = r.get("bgg_id")
        url = r.get("image_url")
        if not url:
            continue

        ext = ".jpg"
        fname = f"{bid}-{hash_url(url)}{ext}"
        path = OUT / fname

        if path.exists():
            continue

        try:
            img = requests.get(url, timeout=20)
            if img.status_code == 200:
                path.write_bytes(img.content)
                print("[OK] saved", fname)
        except:
            print("[ERR] download fail", bid)

if __name__ == "__main__":
    main()

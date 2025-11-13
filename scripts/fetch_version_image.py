# scripts/fetch_version_image.py
import os, json, time, requests, xml.etree.ElementTree as ET
from pathlib import Path

INOUT = Path("data/bgg_data.json")
API   = "https://boardgamegeek.com/xmlapi2/thing"

UA = os.getenv("BGG_UA", "game-guide-site/ci (+https://github.com/TELIFUJ/game-guide-site)")
TOKEN = os.getenv("BGG_TOKEN", "").strip()

HEADERS = {
    "User-Agent": UA,
    "Accept": "application/xml",
    "Referer": "https://boardgamegeek.com/",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

def _get(url, params=None, backoff=2, attempt=1, max_attempts=8):
    r = requests.get(url, params=params, timeout=60, headers=HEADERS)
    if r.status_code in (202, 429, 500, 502, 503, 504) and attempt < max_attempts:
        time.sleep(backoff)
        return _get(url, params, min(backoff * 1.7, 16), attempt + 1, max_attempts)
    r.raise_for_status()
    return r

def fetch_version(v_id: int):
    r = _get(API, params={"type": "boardgameversion", "id": str(v_id)})
    root = ET.fromstring(r.text)
    it   = root.find("item")
    if it is None: return None
    img = it.find("image"); thumb = it.find("thumbnail")
    return (img.text if img is not None else None) or (thumb.text if thumb is not None else None)

def main():
    if not INOUT.exists():
        print("No data/bgg_data.json; skip."); return

    rows = json.loads(INOUT.read_text(encoding="utf-8"))
    changed = False

    for r in rows:
        if r.get("image_override"):  # 尊重 override
            continue

        raw = r.get("image_version_id")
        v = (raw or "").strip() if isinstance(raw, str) else (str(raw).strip() if raw is not None else "")
        if not v: continue

        try:
            vid = int(v)
        except Exception:
            print(f"Skip invalid image_version_id: {v}")
            continue

        try:
            url = fetch_version(vid)
            if url:
                r["image_url"] = url
                r["image_version_used"] = vid
                changed = True
                print(f"Using version {vid} image for bgg_id={r.get('bgg_id') or r.get('id')}")
            else:
                print(f"No image for version {vid}")
        except Exception as e:
            print(f"Version fetch failed {vid}: {e}")

    if changed:
        INOUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print("fetch_version_image: updated data/bgg_data.json")
    else:
        print("fetch_version_image: no change")

if __name__ == "__main__":
    main()

# scripts/fetch_version_image.py
import json, time, requests, xml.etree.ElementTree as ET
from pathlib import Path

INOUT = Path("data/bgg_data.json")
API = "https://boardgamegeek.com/xmlapi2/thing?type=boardgameversion&id="

def fetch_version(v_id: int):
    url = API + str(v_id)
    r = requests.get(url, timeout=60)
    # BGG 會回 202 表示「資料準備中」；要輪詢直到不是 202
    while r.status_code == 202:
        time.sleep(2)
        r = requests.get(url, timeout=60)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    it = root.find("item")
    if it is None:
        return None
    img = it.find("image")
    thumb = it.find("thumbnail")
    return (img.text if img is not None else None) or (thumb.text if thumb is not None else None)

def main():
    if not INOUT.exists():
        print("No data/bgg_data.json; skip.")
        return

    rows = json.loads(INOUT.read_text(encoding="utf-8"))
    changed = False

    for r in rows:
        raw = r.get("image_version_id")
        v = (raw or "").strip() if isinstance(raw, str) else (str(raw).strip() if raw is not None else "")
        if not v:
            continue

        try:
            vid = int(v)
        except:
            print(f"Skip invalid image_version_id: {v}")
            continue

        try:
            url = fetch_version(vid)
            if url:
                r["image_url"] = url
                r["image_version_used"] = vid
                changed = True
                print(f"Using version {vid} image for bgg_id={r.get('bgg_id')}")
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

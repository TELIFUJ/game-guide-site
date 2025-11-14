#!/usr/bin/env python3
import os, time, json, pathlib, requests
from lxml import etree

ROOT = pathlib.Path(__file__).resolve().parents[1]
IDS = ROOT / "data" / "bgg_ids.txt"
OUT = ROOT / "data" / "bgg_data.json"

API_KEY = os.getenv("BGG_API_KEY")

HEADERS = {
    "User-Agent": "BoardGameGuide/1.0 (GitHub Actions)",
    "Accept": "application/xml",
    "Authorization": f"Bearer {API_KEY}",
}

def fetch_one(bid):
    url = f"https://api.geekdo.com/xmlapi2/thing?id={bid}&stats=1"
    for i in range(5):
        r = requests.get(url, headers=HEADERS)
        if r.status_code == 200:
            return r.text
        time.sleep(1 + i)
    return None

def main():
    ids = [x.strip() for x in IDS.read_text().splitlines() if x.strip()]
    data = []

    for i, bid in enumerate(ids, 1):
        print(f"[{i}/{len(ids)}] Fetch id={bid}")
        xml = fetch_one(bid)
        if not xml:
            data.append({"bgg_id": bid, "error": 1})
            continue

        root = etree.fromstring(xml.encode("utf-8"))
        item = root.find("item")
        if item is None:
            data.append({"bgg_id": bid, "error": 1})
            continue

        name = item.find('name[@type="primary"]')
        image = item.find("image")

        row = {
            "bgg_id": int(bid),
            "name_en": name.get("value") if name is not None else None,
            "image_url": image.text if image is not None else None,
        }

        data.append(row)
        time.sleep(0.2)

    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    print(f"[OK] wrote {OUT}")

if __name__ == "__main__":
    main()

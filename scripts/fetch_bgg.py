# scripts/fetch_bgg.py
import time, json, requests, xml.etree.ElementTree as ET
from pathlib import Path

INPUT = Path("data/bgg_ids.json")
OUTPUT = Path("data/bgg_data.json")

API = "https://boardgamegeek.com/xmlapi2/thing?stats=1&id="

def fetch_one(bgg_id: int):
    url = API + str(bgg_id)
    r = requests.get(url, timeout=30)
    # BGG 排隊時會回 202，要輪詢
    while r.status_code == 202:
        time.sleep(2)
        r = requests.get(url, timeout=30)
    r.raise_for_status()
    return ET.fromstring(r.text)

def parse_item(root: ET.Element):
    item = root.find("item")
    if item is None:
        return {}
    def get_attr(tag, attr="value", default=None):
        el = item.find(tag)
        return el.get(attr) if (el is not None and el.get(attr) is not None) else default

    # 名稱（primary）
    name_en = None
    for n in item.findall("name"):
        if n.get("type") == "primary":
            name_en = n.get("value")
            break

    # 分類 / 機制
    categories = [x.get("value") for x in item.findall("link[@type='boardgamecategory']")]
    mechanics  = [x.get("value") for x in item.findall("link[@type='boardgamemechanic']")]

    # 欄位
    year   = get_attr("yearpublished")
    min_p  = get_attr("minplayers")
    max_p  = get_attr("maxplayers")
    min_t  = get_attr("minplaytime")
    max_t  = get_attr("maxplaytime")
    weight = get_attr("statistics/ratings/averageweight")

    image_el = item.find("image")
    thumb_el = item.find("thumbnail")
    image_url = image_el.text if image_el is not None else None
    thumb_url = thumb_el.text if thumb_el is not None else None

    return {
        "name_en": name_en,
        "year": int(year) if year else None,
        "players": [int(min_p) if min_p else None, int(max_p) if max_p else None],
        "time_min": int(min_t) if min_t else None,
        "time_max": int(max_t) if max_t else None,
        "weight": float(weight) if weight else None,
        "categories": categories,
        "mechanics": mechanics,
        "image_url": image_url or thumb_url,
        "thumb_url": thumb_url or image_url
    }

def main():
    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    out = []
    for r in rows:
        bid = r.get("bgg_id")
        if not bid:
            out.append({**r})  # 沒有 bgg_id 就原樣帶過去
            continue
        try:
            root = fetch_one(int(bid))
            parsed = parse_item(root)
            merged = {**r, **parsed}
            out.append(merged)
            time.sleep(2.5)  # 禮貌限流
        except Exception as e:
            print(f"Failed bgg_id={bid}: {e}")
            out.append({**r})
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fetched {len(out)} entries → {OUTPUT}")

if __name__ == "__main__":
    main()

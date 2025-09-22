import requests, time, json, xml.etree.ElementTree as ET
from pathlib import Path

INPUT = Path("data/bgg_ids.json")
OUTPUT = Path("data/bgg_data.json")
API_BASE = "https://boardgamegeek.com/xmlapi2/thing?stats=1&versions=1&id="
BATCH = 20

def fetch_batch(ids):
    url = API_BASE + ",".join(str(i) for i in ids)
    r = requests.get(url, timeout=60)
    while r.status_code == 202:
        time.sleep(2)
        r = requests.get(url, timeout=60)
    r.raise_for_status()
    return ET.fromstring(r.text)

def parse_items(root):
    out=[]
    for item in root.findall("item"):
        try:
            bid=int(item.get("id"))
        except:
            continue
        name_en=None
        for n in item.findall("name"):
            if n.get("type")=="primary":
                name_en=n.get("value"); break

        def val(tag, attr="value"):
            el=item.find(tag)
            return el.get(attr) if el is not None and el.get(attr) is not None else None

        avgw=item.find("statistics/ratings/averageweight")
        weight=float(avgw.get("value")) if avgw is not None and avgw.get("value") not in (None,"NaN") else None
        image_el=item.find("image"); thumb_el=item.find("thumbnail")
        image_url=image_el.text if image_el is not None else None
        thumb_url=thumb_el.text if thumb_el is not None else None
        categories=[l.get("value") for l in item.findall("link[@type='boardgamecategory']")]
        mechanics=[l.get("value") for l in item.findall("link[@type='boardgamemechanic']")]
        versions_el=item.find("versions")
        versions_count=len(versions_el.findall("item")) if versions_el is not None else 0
        out.append({
            "bgg_id": bid,
            "name_en": name_en,
            "year": int(val("yearpublished")) if val("yearpublished") else None,
            "players": [int(val("minplayers")) if val("minplayers") else None,
                        int(val("maxplayers")) if val("maxplayers") else None],
            "time_min": int(val("minplaytime")) if val("minplaytime") else None,
            "time_max": int(val("maxplaytime")) if val("maxplaytime") else None,
            "weight": weight,
            "categories": categories,
            "mechanics": mechanics,
            "image_url": image_url or thumb_url,
            "thumb_url": thumb_url or image_url,
            "versions_count": versions_count,
        })
    return out

def main():
    if not INPUT.exists():
        print("No data/bgg_ids.json; nothing to fetch."); return

    base_rows=json.loads(INPUT.read_text(encoding="utf-8"))

    # 允許同一 bgg_id 多筆：by_id 變成 list
    by_id={}  # {bid: [row,row2,...]}
    seen=set()
    ids=[]
    for r in base_rows:
        bid=r.get("bgg_id")
        if not bid: continue
        bid=int(bid)
        by_id.setdefault(bid, []).append(r)
        if bid not in seen:
            ids.append(bid); seen.add(bid)

    results=[]
    for i in range(0,len(ids),BATCH):
        chunk=ids[i:i+BATCH]
        try:
            root=fetch_batch(chunk)
            parsed=parse_items(root)
            for p in parsed:
                # 對同一 ID 的每筆 base row 各自 merge，輸出多列
                src_list = by_id.get(int(p["bgg_id"]), [{}])
                for src in src_list:
                    results.append({**src,**p})
        except Exception as e:
            print(f"Batch {chunk} failed: {e}")
        time.sleep(3)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fetched {len(results)} entries → {OUTPUT}")

if __name__ == "__main__":
    main()

# scripts/fetch_bgg.py
import json, time, requests, xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

INPUT   = Path("data/bgg_ids.json")
OUTPUT  = Path("data/bgg_data.json")
API_THING = "https://boardgamegeek.com/xmlapi2/thing"
BATCH   = 50

def fetch_batch(ids, backoff=2):
    params = {
        "id": ",".join(str(i) for i in ids),
        "type": "boardgame",
        "stats": "1"
    }
    r = requests.get(API_THING, params=params, timeout=60)
    while r.status_code == 202:
        time.sleep(backoff)
        r = requests.get(API_THING, params=params, timeout=60)
        backoff = min(backoff * 2, 16)
    r.raise_for_status()
    return ET.fromstring(r.text)

def _text(it, tag):
    el = it.find(tag)
    return el.text if el is not None else None

def parse_items(root):
    out = []
    for it in root.findall("item"):
        try:
            bid = int(it.get("id"))
        except:
            continue
        name_el = it.find("name[@type='primary']")
        name_en = name_el.get("value") if name_el is not None else None

        def _int(t):
            try:
                return int(t) if t not in (None, "", "0") else None
            except:
                return None

        def _float(t):
            try:
                v = float(t)
                return v if v > 0 else None
            except:
                return None

        year        = _int(_text(it, "yearpublished"))
        minplayers  = _int(_text(it, "minplayers"))
        maxplayers  = _int(_text(it, "maxplayers"))
        minplaytime = _int(_text(it, "minplaytime"))
        maxplaytime = _int(_text(it, "maxplaytime"))
        playingtime = _int(_text(it, "playingtime"))
        image       = _text(it, "image")
        thumb       = _text(it, "thumbnail")

        weight_el   = it.find("statistics/ratings/averageweight")
        weight      = _float(weight_el.get("value")) if weight_el is not None else None

        cats  = [ln.get("value") for ln in it.findall("link[@type='boardgamecategory']")]
        mechs = [ln.get("value") for ln in it.findall("link[@type='boardgamemechanic']")]

        out.append({
            "bgg_id": bid,
            "name_en": name_en,
            "year": year,
            "players": None,       # (可留空；前端目前未用)
            "time_min": minplaytime or playingtime,
            "time_max": maxplaytime or playingtime,
            "weight": weight,
            "categories": cats,
            "mechanics": mechs,
            "image_url": image,
            "thumb_url": thumb,
            "bgg_url": f"https://boardgamegeek.com/boardgame/{bid}"
        })
    return out

def main():
    if not INPUT.exists():
        print("No data/bgg_ids.json; nothing to fetch."); return

    base_rows = json.loads(INPUT.read_text(encoding="utf-8"))
    # 讓「同一 bgg_id 多列」在這層 fan-out
    rows_by_id = defaultdict(list)
    ids_unique = []
    for base in base_rows:
        bid = base.get("bgg_id")
        if not bid: continue
        try:
            bid = int(bid)
        except:
            continue
        rows_by_id[bid].append(base)
        if bid not in ids_unique:
            ids_unique.append(bid)

    results = []
    for i in range(0, len(ids_unique), BATCH):
        chunk = ids_unique[i:i+BATCH]
        try:
            root   = fetch_batch(chunk)
            parsed = parse_items(root)   # 每個 id 只回來 1 筆
            for p in parsed:
                bid = int(p["bgg_id"])
                bases = rows_by_id.get(bid, [{}])
                # fan-out：一個 BGG 筆 N 個 base → 產 N 筆
                for base in bases:
                    results.append({**p, **base})
        except Exception as e:
            print(f"Batch {chunk} failed: {e}")
        time.sleep(2)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fetched {len(results)} entries → {OUTPUT}")

if __name__ == "__main__":
    main()

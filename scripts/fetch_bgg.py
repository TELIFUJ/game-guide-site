# scripts/fetch_bgg.py
import os, requests, time, json, xml.etree.ElementTree as ET
from pathlib import Path

INPUT  = Path("data/bgg_ids.json")
OUTDIR = Path("data")

API_BASE = "https://boardgamegeek.com/xmlapi2/thing?stats=1&versions=1&id="
BATCH = 20

# 可選的「分片」環境變數；沒設就當 1 片
SHARD_INDEX = int(os.getenv("SHARD_INDEX", "0"))
SHARD_COUNT = int(os.getenv("SHARD_COUNT", "1"))
OUTFILE = OUTDIR / (f"bgg_data_shard_{SHARD_INDEX}.json" if SHARD_COUNT > 1 else "bgg_data.json")

def get_with_backoff(url, timeout=60, max_sleep=60):
    """對 202/429/5xx 進行退避重試。"""
    sleep = 2
    while True:
        r = requests.get(url, timeout=timeout)
        # 202: BGG 排隊
        if r.status_code == 202:
            time.sleep(2)
            continue
        # 限流/暫時錯誤：退避
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(sleep)
            sleep = min(max_sleep, sleep * 2)
            continue
        r.raise_for_status()
        return r

def fetch_batch(ids):
    url = API_BASE + ",".join(str(i) for i in ids)
    r = get_with_backoff(url)
    return ET.fromstring(r.text)

def parse_items(root):
    out = []
    for item in root.findall("item"):
        try:
            bid = int(item.get("id"))
        except:
            continue
        # primary EN
        name_en = None
        for n in item.findall("name"):
            if n.get("type") == "primary":
                name_en = n.get("value"); break

        def val(tag, attr="value"):
            el = item.find(tag)
            return el.get(attr) if el is not None and el.get(attr) is not None else None

        avgw = item.find("statistics/ratings/averageweight")
        weight = float(avgw.get("value")) if avgw is not None and avgw.get("value") not in (None, "NaN") else None

        image_el = item.find("image"); thumb_el = item.find("thumbnail")
        image_url = image_el.text if image_el is not None else None
        thumb_url = thumb_el.text if thumb_el is not None else None

        categories = [l.get("value") for l in item.findall("link[@type='boardgamecategory']")]
        mechanics  = [l.get("value") for l in item.findall("link[@type='boardgamemechanic']")]

        versions_el = item.find("versions")
        versions_count = len(versions_el.findall("item")) if versions_el is not None else 0

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
        print("No data/bgg_ids.json; nothing to fetch.")
        return

    base_rows = json.loads(INPUT.read_text(encoding="utf-8"))
    by_id, ids = {}, []
    for r in base_rows:
        bid = r.get("bgg_id")
        if not bid:
            continue
        bid = int(bid)
        ids.append(bid)
        by_id[bid] = r

    # 分片：用索引取餘數；沒啟用時等於 ids 本身
    ids_shard = [bid for idx, bid in enumerate(ids) if idx % SHARD_COUNT == SHARD_INDEX]
    print(f"Total IDs={len(ids)}; shard[{SHARD_INDEX}/{SHARD_COUNT}] -> {len(ids_shard)}")

    results = []
    for i in range(0, len(ids_shard), BATCH):
        chunk = ids_shard[i:i+BATCH]
        try:
            root = fetch_batch(chunk)
            parsed = parse_items(root)
            for p in parsed:
                src = by_id.get(int(p["bgg_id"]), {})
                results.append({**src, **p})
        except Exception as e:
            # 繼續後面批次
            print(f"Batch {chunk[:3]}..(len={len(chunk)}) failed: {e}")
        time.sleep(2)  # 禮貌等待

    OUTDIR.mkdir(parents=True, exist_ok=True)
    OUTFILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fetched {len(results)} entries → {OUTFILE}")

if __name__ == "__main__":
    main()

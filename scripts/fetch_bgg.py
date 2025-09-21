# scripts/fetch_bgg.py（只示範修改重點）
import os, requests, time, json, xml.etree.ElementTree as ET
from pathlib import Path

INPUT  = Path("data/bgg_ids.json")
OUTDIR = Path("data")
API_BASE = "https://boardgamegeek.com/xmlapi2/thing?stats=1&versions=1&id="
BATCH = 20

SHARD_INDEX = int(os.getenv("SHARD_INDEX", "0"))
SHARD_COUNT = int(os.getenv("SHARD_COUNT", "1"))
OUTFILE = OUTDIR / (f"bgg_data_shard_{SHARD_INDEX}.json" if SHARD_COUNT>1 else "bgg_data.json")

def get_with_backoff(url, timeout=60, max_sleep=60):
    sleep = 2
    while True:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 202:
            time.sleep(2); continue
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(sleep); sleep = min(max_sleep, sleep*2); continue
        r.raise_for_status()
        return r

def fetch_batch(ids):
    url = API_BASE + ",".join(str(i) for i in ids)
    r = get_with_backoff(url)
    return ET.fromstring(r.text)

# ...（parse_items 與你原本相同）...

def main():
    if not INPUT.exists():
        print("No data/bgg_ids.json; nothing to fetch."); return

    base_rows = json.loads(INPUT.read_text(encoding="utf-8"))
    by_id, ids = {}, []
    for r in base_rows:
        bid = r.get("bgg_id")
        if not bid: continue
        bid = int(bid)
        ids.append(bid)
        by_id[bid] = r

    # 依 shard 取子集合（按索引取餘數）
    ids_shard = [bid for idx, bid in enumerate(ids) if idx % SHARD_COUNT == SHARD_INDEX]
    print(f"Total IDs={len(ids)}; shard[{SHARD_INDEX}/{SHARD_COUNT}] -> {len(ids_shard)}")

    results=[]
    for i in range(0, len(ids_shard), BATCH):
        chunk = ids_shard[i:i+BATCH]
        try:
            root = fetch_batch(chunk)
            parsed = parse_items(root)
            for p in parsed:
                src = by_id.get(int(p["bgg_id"]), {})
                results.append({**src, **p})
        except Exception as e:
            print(f"Batch {chunk[:3]}.. len={len(chunk)} failed: {e}")
        time.sleep(2)  # 禮貌等待

    OUTDIR.mkdir(parents=True, exist_ok=True)
    OUTFILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fetched {len(results)} entries → {OUTFILE}")

if __name__ == "__main__":
    main()

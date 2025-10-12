# scripts/fetch_comments.py
import json, time, requests, xml.etree.ElementTree as ET
from pathlib import Path
INOUT = Path("data/bgg_data.json")

API = "https://boardgamegeek.com/xmlapi2/thing?id={id}&comments=1&pagesize=20"

def fetch_comments(bid, backoff=1.5):
    url = API.format(id=bid)
    r = requests.get(url, timeout=60)
    while r.status_code == 202:
        time.sleep(backoff); r = requests.get(url, timeout=60)
    if r.status_code == 429:
        time.sleep(backoff); return fetch_comments(bid, min(backoff*2, 12))
    r.raise_for_status()
    root = ET.fromstring(r.text)
    it = root.find("item")
    if it is None: return []
    cmts = []
    for c in it.findall("comments/comment"):
        cmts.append({
            "username": c.get("username") or "",
            "rating":   (float(c.get("rating")) if (c.get("rating") and c.get("rating") not in ("", "N/A")) else None),
            "date":     c.get("date") or "",
            "text":     c.get("value") or ""
        })
    return cmts

def main():
    if not INOUT.exists():
        print("No data/bgg_data.json; skip comments."); return
    rows = json.loads(INOUT.read_text(encoding="utf-8"))

    # 依 id 聚合，避免重抓
    from collections import defaultdict
    ids = []
    for r in rows:
        bid = r.get("bgg_id")
        if bid and bid not in ids:
            ids.append(bid)

    by_id_comments = {}
    for i, bid in enumerate(ids, 1):
        try:
            cmts = fetch_comments(bid)
            # 排序：先有評分的在前（高到低），再比字數長度
            cmts.sort(key=lambda x: (x["rating"] is None, -(x["rating"] or 0), -len(x["text"])))
            by_id_comments[bid] = cmts[:20]  # 保留 20 以備前端需要更多
            print(f"[{i}/{len(ids)}] comments for {bid}: {len(cmts)}")
            time.sleep(0.7)
        except Exception as e:
            print(f"comments failed for {bid}: {e}")

    # 精選前 3 則給 comments_top
    for r in rows:
        bid = r.get("bgg_id")
        if not bid: continue
        cmts = by_id_comments.get(bid, [])
        r["comments_top"] = cmts[:3]

    INOUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("fetch_comments: done and saved to data/bgg_data.json")

if __name__ == "__main__":
    main()

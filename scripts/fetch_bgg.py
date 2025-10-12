# scripts/fetch_bgg.py
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
        time.sleep(2); r = requests.get(url, timeout=60)
    r.raise_for_status()
    return ET.fromstring(r.text)

def _num(val):
    try:
        if val in (None, "", "Not Ranked", "NaN"): return None
        return int(val) if str(val).isdigit() else float(val)
    except: return None

def parse_items(root):
    out=[]
    for item in root.findall("item"):
        try: bid=int(item.get("id"))
        except: continue

        # 名稱
        name_en=None
        for n in item.findall("name"):
            if n.get("type")=="primary":
                name_en=n.get("value"); break

        # 常用欄位
        def val(tag, attr="value"):
            el=item.find(tag)
            return el.get(attr) if el is not None and el.get(attr) is not None else None

        avgw=item.find("statistics/ratings/averageweight")
        weight=_num(avgw.get("value")) if avgw is not None else None

        image_el=item.find("image"); thumb_el=item.find("thumbnail")
        image_url=image_el.text if image_el is not None else None
        thumb_url=thumb_el.text if thumb_el is not None else None

        categories=[l.get("value") for l in item.findall("link[@type='boardgamecategory']")]
        mechanics=[l.get("value") for l in item.findall("link[@type='boardgamemechanic']")]

        versions_el=item.find("versions")
        versions_count=len(versions_el.findall("item")) if versions_el is not None else 0

        # ====== 評分／排名 ======
        ratings = item.find("statistics/ratings")
        rating_avg = rating_bayes = ratings_count = comments_count = None
        rank_overall = rank_strategy = None
        if ratings is not None:
            a = ratings.find("average"); b = ratings.find("bayesaverage")
            users = ratings.find("usersrated"); com = ratings.find("numcomments")
            rating_avg    = _num(a.get("value") if a is not None else None)
            rating_bayes  = _num(b.get("value") if b is not None else None)
            ratings_count = _num(users.get("value") if users is not None else None)
            comments_count= _num(com.get("value") if com is not None else None)
            ranks = ratings.find("ranks")
            if ranks is not None:
                for rk in ranks.findall("rank"):
                    name = rk.get("name"); val = rk.get("value")
                    if name == "boardgame":
                        rank_overall = _num(val)
                    elif name == "strategygames":
                        rank_strategy = _num(val)

        out.append({
            "bgg_id": bid,
            "name_en": name_en,
            "year": _num(val("yearpublished")),
            "players": [_num(val("minplayers")), _num(val("maxplayers"))],
            "time_min": _num(val("minplaytime")),
            "time_max": _num(val("maxplaytime")),
            "weight": weight,
            "categories": categories,
            "mechanics": mechanics,
            "image_url": image_url or thumb_url,
            "thumb_url": thumb_url or image_url,
            "versions_count": versions_count,
            "rating_avg": rating_avg,
            "rating_bayes": rating_bayes,
            "ratings_count": ratings_count,
            "comments_count": comments_count,
            "rank_overall": rank_overall,
            "rank_strategy": rank_strategy,
        })
    return out

def main():
    if not INPUT.exists():
        print("No data/bgg_ids.json; nothing to fetch."); return
    base_rows=json.loads(INPUT.read_text(encoding="utf-8"))

    from collections import defaultdict
    rows_by_id = defaultdict(list)
    ids_unique = []
    for r in base_rows:
        bid = r.get("bgg_id")
        if not bid: continue
        bid = int(bid)
        rows_by_id[bid].append(r)
        if bid not in ids_unique: ids_unique.append(bid)

    results=[]
    for i in range(0,len(ids_unique),BATCH):
        chunk=ids_unique[i:i+BATCH]
        try:
            root=fetch_batch(chunk)
            parsed=parse_items(root)
            for p in parsed:
                bid=int(p["bgg_id"])
                bases = rows_by_id.get(bid,[{}])
                for base in bases:
                    results.append({**base, **p})
        except Exception as e:
            print(f"Batch {chunk} failed: {e}")
        time.sleep(3)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fetched {len(results)} entries → {OUTPUT}")

if __name__ == "__main__": main()

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

def _num(v, t=float):
    if v in (None, "", "NaN", "not ranked", "Not Ranked", "0.0"):
        return None
    try:
        return t(v)
    except Exception:
        return None

def parse_items(root):
    out=[]
    for item in root.findall("item"):
        try: bid=int(item.get("id"))
        except: continue

        # 基本
        name_en=None
        for n in item.findall("name"):
            if n.get("type")=="primary":
                name_en=n.get("value"); break

        def val(tag, attr="value"):
            el=item.find(tag)
            return el.get(attr) if el is not None and el.get(attr) is not None else None

        # 策略強度
        avgw=item.find("statistics/ratings/averageweight")
        weight=_num(avgw.get("value")) if avgw is not None else None

        # ★ 評分（平均 / Bayesian）
        r_avg_el   = item.find("statistics/ratings/average")
        r_bayes_el = item.find("statistics/ratings/bayesaverage")
        rating_avg   = _num(r_avg_el.get("value"))   if r_avg_el   is not None else None
        rating_bayes = _num(r_bayes_el.get("value")) if r_bayes_el is not None else None

        # ★ 排名（整體）
        rank_overall = None
        ranks_el = item.find("statistics/ratings/ranks")
        if ranks_el is not None:
            for rk in ranks_el.findall("rank"):
                nm = rk.get("name") or ""
                if nm in ("boardgame", "boardgameoverall"):
                    rank_overall = _num(rk.get("value"), int)
                    break

        # 其他
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
            "year": _num(val("yearpublished"), int),
            "players": [_num(val("minplayers"), int), _num(val("maxplayers"), int)],
            "time_min": _num(val("minplaytime"), int),
            "time_max": _num(val("maxplaytime"), int),
            "weight": weight,
            "rating_avg": rating_avg,
            "rating_bayes": rating_bayes,
            "rank_overall": rank_overall,
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

    # fan-out：同一 bgg_id 可能對應多列
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

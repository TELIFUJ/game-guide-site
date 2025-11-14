#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fetch_bgg.py — Clean-Safe 版（2025）
速度快、不中斷、log 乾淨
抓不到的直接跳過，不 retry storm。
"""

import json, time, pathlib, requests
from lxml import etree

ROOT = pathlib.Path(__file__).resolve().parents[1]
IDS_FILE = ROOT / "data" / "bgg_ids.json"
OUT_FILE = ROOT / "data" / "bgg_data.json"

HOST = "https://boardgamegeek.com/xmlapi2/thing"
HEADERS = {"User-Agent": "BoardGameGuide-Fetch/1.0"}

def safe_request(batch):
    """乾淨的請求，不 retry storm，失敗就跳過"""
    try:
        r = requests.get(
            HOST,
            params={
                "id": ",".join(str(i) for i in batch),
                "stats": 1
            },
            headers=HEADERS,
            timeout=12
        )
        if r.status_code != 200:
            print("跳過 batch（HTTP）:", batch)
            return None
        return r.text
    except Exception as e:
        print("跳過 batch（例外）:", batch, e)
        return None


def parse_items(xml_text):
    """解析 XML"""
    if not xml_text:
        return []

    out = []
    root = etree.fromstring(xml_text.encode("utf-8"))

    for item in root.xpath("//item"):
        gid = int(item.get("id"))
        name = ""
        name_zh = None

        for n in item.xpath("./name"):
            val = n.get("value") or ""
            if n.get("type") == "primary":
                name = val
            if any("\u4e00" <= c <= "\u9fff" for c in val):
                name_zh = val

        year = item.xpath("./yearpublished/@value")
        year = int(year[0]) if year else None

        # stats
        stats = item.xpath("./statistics/ratings")
        if stats:
            stats = stats[0]
            def getf(p):
                try: return float(stats.xpath(p)[0])
                except: return None

            def geti(p):
                try: return int(stats.xpath(p)[0])
                except: return None

            rating_bayes = getf("./bayesaverage/@value")
            rating_avg = getf("./average/@value")
            users_rated = geti("./usersrated/@value")
            weight = getf("./averageweight/@value")
        else:
            rating_bayes = rating_avg = users_rated = weight = None

        # categories / mechanisms
        categories = [l.get("value") for l in item.xpath("./link[@type='boardgamecategory']")]
        mechanisms = [l.get("value") for l in item.xpath("./link[@type='boardgamemechanic']")]

        # images
        image = (item.xpath("./image/text()") or [None])[0]
        thumb = (item.xpath("./thumbnail/text()") or [None])[0]

        out.append({
            "bgg_id": gid,
            "name": name,
            "name_zh": name_zh,
            "year": year,
            "rating_bayes": rating_bayes,
            "rating_avg": rating_avg,
            "users_rated": users_rated,
            "weight": weight,
            "categories": categories,
            "mechanisms": mechanisms,
            "image": image,
            "thumbnail": thumb,
            "source": "bgg"
        })

    return out


def main():
    if not IDS_FILE.exists():
        print("找不到 bgg_ids.json")
        return

    raw = json.loads(IDS_FILE.read_text("utf-8"))

    # 取出所有數字 BGG ID
    ids = []
    for x in raw:
        if isinstance(x, int):
            ids.append(x)
        elif isinstance(x, dict) and "bgg_id" in x:
            ids.append(x["bgg_id"])

    print("[OK] Valid BGG IDs:", len(ids))

    results = []
    BATCH = 10  # 小批次 → 不會卡

    for i in range(0, len(ids), BATCH):
        batch = ids[i:i+BATCH]
        xml = safe_request(batch)
        items = parse_items(xml)
        results.extend(items)
        time.sleep(0.8)

    OUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), "utf-8")
    print("[OK] Done → data/bgg_data.json")


if __name__ == "__main__":
    main()

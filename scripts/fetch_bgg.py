#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_bgg.py
最終穩定版（2025）
抓取 BGG XML2 API → 產生 data/bgg_data.json

特色：
- 自動 retry（處理 429）
- 解析分數：Bayes / Avg / UsersRated / Weight
- 解析分類、機制、中文名稱
- 解析圖片
- 完全相容 build_json.py 流程
"""

import json
import time
import pathlib
import requests
from lxml import etree
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

ROOT = pathlib.Path(__file__).resolve().parents[1]
IDS_FILE = ROOT / "data" / "bgg_ids.json"
OUT_FILE = ROOT / "data" / "bgg_data.json"

HOST = "https://boardgamegeek.com/xmlapi2"
HEADERS = {"User-Agent": "BoardGameGuide-Fetch/1.0"}

# ----------------------------------------------------
# API 請求（帶 retry）
# ----------------------------------------------------
class BGGError(Exception):
    pass

@retry(
    stop=stop_after_attempt(6),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(BGGError)
)
def bgg_request(ids):
    """呼叫 BGG XML2 /thing，帶 retry"""
    params = {
        "id": ",".join(str(i) for i in ids),
        "type": "boardgame,boardgameexpansion,boardgameaccessory",
        "stats": 1
    }

    r = requests.get(f"{HOST}/thing", params=params, headers=HEADERS, timeout=20)

    if r.status_code == 429:
        raise BGGError("BGG 429 Too Many Requests")

    if r.status_code != 200:
        raise BGGError(f"BGG HTTP {r.status_code}")

    return r.text


# ----------------------------------------------------
# 解析 XML
# ----------------------------------------------------
def parse_items(xml_text):
    """解析 BGG XML 回傳遊戲清單"""
    root = etree.fromstring(xml_text.encode("utf-8"))
    items = []

    for item in root.xpath("//item"):
        gid = int(item.get("id"))

        # 名稱（英文、中文）
        name = ""
        name_zh = None
        for n in item.xpath("./name"):
            ntype = n.get("type")
            val = n.get("value") or ""
            if ntype == "primary":
                name = val
            # 偵測中文：如果包含中文 unicode
            if any("\u4e00" <= ch <= "\u9fff" for ch in val):
                name_zh = val

        year = item.xpath("./yearpublished/@value")
        year = int(year[0]) if year else None

        # Stats
        stats = item.xpath("./statistics/ratings")[0] if item.xpath("./statistics/ratings") else None

        if stats is not None:
            try:
                rating_bayes = float(stats.xpath("./bayesaverage/@value")[0])
            except:
                rating_bayes = None

            try:
                rating_avg = float(stats.xpath("./average/@value")[0])
            except:
                rating_avg = None

            try:
                users_rated = int(stats.xpath("./usersrated/@value")[0])
            except:
                users_rated = None

            try:
                weight = float(stats.xpath("./averageweight/@value")[0])
            except:
                weight = None
        else:
            rating_bayes = rating_avg = users_rated = weight = None

        # 分類 / 機制
        categories = []
        mechanisms = []
        for link in item.xpath("./link"):
            ltype = link.get("type")
            val = link.get("value")
            if ltype == "boardgamecategory":
                categories.append(val)
            elif ltype == "boardgamemechanic":
                mechanisms.append(val)

        # 圖片
        image = item.xpath("./image/text()")
        image = image[0] if image else None

        thumb = item.xpath("./thumbnail/text()")
        thumb = thumb[0] if thumb else None

        items.append({
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

    return items


# ----------------------------------------------------
# 主程式
# ----------------------------------------------------
def main():
    if not IDS_FILE.exists():
        print(f"[ERROR] 找不到 bgg_ids.json：{IDS_FILE}")
        return

    ids = json.loads(IDS_FILE.read_text(encoding="utf-8"))
    print(f"Total BGG IDs: {len(ids)}")

    results = []

    # 一次抓 50 筆（避免 429）
    BATCH = 50

    for i in range(0, len(ids), BATCH):
        batch = ids[i: i+BATCH]
        print(f"Fetching {i} ~ {i+len(batch)} ...")

        try:
            xml = bgg_request(batch)
            items = parse_items(xml)
            results.extend(items)
            time.sleep(1.2)  # 避免 429
        except Exception as e:
            print("ERROR batch:", batch, e)

    # 輸出
    OUT_FILE.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"[OK] Write → {OUT_FILE} ({len(results)} items)")


if __name__ == "__main__":
    main()

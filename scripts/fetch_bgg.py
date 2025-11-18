#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_bgg.py — 用 XML API2 取回 BGG 資料（含評分／分類／機制／人數／時間）

流程：
1) 從 data/bgg_ids.txt 讀取所有 BGG ID（由 extract_from_csv.py 產生）
2) 依規則「每批最多 20 個 id」呼叫：
   https://boardgamegeek.com/xmlapi2/thing?id=...&stats=1&type=boardgame,boardgameexpansion
3) 解析 XML → 存成 data/bgg_data.json

說明：
- 若有 data/bgg_token.txt，會讀裡面的 Token，塞進 Authorization: Bearer <token> header
- 若沒有 token，一樣可以匿名呼叫（只是理論上配額比較低）
"""

import json
import pathlib
import time
from typing import List, Dict, Optional

import requests
from lxml import etree

ROOT = pathlib.Path(__file__).resolve().parents[1]
IDS_TXT = ROOT / "data" / "bgg_ids.txt"
OUT_JSON = ROOT / "data" / "bgg_data.json"
TOKEN_FILE = ROOT / "data" / "bgg_token.txt"

# 一批最多 20 個（XML API2 規則）
BATCH_SIZE = 20
SLEEP_SEC = 5.0

# 注意：不要用 www.boardgamegeek.com，會影響授權
BASE_URL = "https://boardgamegeek.com/xmlapi2/thing"


# ------------------------------
# 工具函式
# ------------------------------
def load_token() -> Optional[str]:
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text("utf-8").strip()
        if token:
            print("[INFO] 使用 data/bgg_token.txt 內的 BGG Token")
            return token
    print("[INFO] 找不到 data/bgg_token.txt，改用匿名模式")
    return None


def load_ids() -> List[str]:
    if not IDS_TXT.exists():
        raise SystemExit(f"[ERR] 找不到 {IDS_TXT}，請先跑 scripts/extract_from_csv.py")

    ids: List[str] = []
    for line in IDS_TXT.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ids.append(line)

    print(f"[INFO] 讀到 {len(ids)} 個 BGG ID")
    return ids


def _safe_float(v: Optional[str]) -> Optional[float]:
    if v is None:
        return None
    v = str(v).strip()
    if not v or v.upper() in {"N/A", "NA"}:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _safe_int(v: Optional[str]) -> Optional[int]:
    f = _safe_float(v)
    if f is None:
        return None
    try:
        return int(round(f))
    except ValueError:
        return None


def fetch_batch(session: requests.Session, token: Optional[str], batch_ids: List[str]) -> Optional[bytes]:
    """
    呼叫 XML API2 /thing，注意：
    - 參數是 id=（不是 ids）
    - 一次最多 20 個 id
    - stats=1 才會有評分資料
    """
    params = {
        "id": ",".join(batch_ids),  # 重點 1：這裡一定要是 id（不是 ids）
        "stats": 1,
        "type": "boardgame,boardgameexpansion",
    }

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    while True:
        r = session.get(BASE_URL, params=params, headers=headers, timeout=30)
        if r.status_code == 202:
            print("    [INFO] HTTP 202（排隊中），稍後重試一次...")
            time.sleep(SLEEP_SEC)
            continue

        if r.status_code != 200:
            print(f"    [ERROR] HTTP {r.status_code}，這批 id 被略過：{batch_ids}")
            body = r.text[:200].replace("\n", " ")
            print(f"           回應前 200 字：{body!r}")
            return None

        return r.content


def parse_xml(xml_bytes: bytes) -> List[Dict]:
    """
    把 XML bytes 轉成 list[dict]：
    - 包含：評分、分類、機制
    - 新增：min_players / max_players / min_playtime / max_playtime
    - 圖片：image_url = image or thumbnail
    """
    root = etree.fromstring(xml_bytes)
    out: List[Dict] = []

    for item in root.findall("item"):
        bid = item.get("id")

        # 名稱與年份
        name_node = item.find("name[@type='primary']")
        name = name_node.get("value") if name_node is not None else None

        year_node = item.find("yearpublished")
        year = _safe_int(year_node.get("value")) if year_node is not None else None

        # 玩家數與時間
        def _get_int(tag: str) -> Optional[int]:
            node = item.find(tag)
            return _safe_int(node.get("value")) if node is not None else None

        min_players = _get_int("minplayers")
        max_players = _get_int("maxplayers")
        min_playtime = _get_int("minplaytime")
        max_playtime = _get_int("maxplaytime")

        # 評分區塊
        stats = item.find("statistics/ratings")
        rating_bayes = rating_avg = users_rated = weight = None
        if stats is not None:
            bayes_node = stats.find("bayesaverage")
            avg_node = stats.find("average")
            users_node = stats.find("usersrated")
            weight_node = stats.find("averageweight")

            rating_bayes = _safe_float(bayes_node.get("value")) if bayes_node is not None else None
            rating_avg = _safe_float(avg_node.get("value")) if avg_node is not None else None
            users_rated = _safe_int(users_node.get("value")) if users_node is not None else None
            weight = _safe_float(weight_node.get("value")) if weight_node is not None else None

        # 分類／機制
        categories = [lnk.get("value") for lnk in item.findall("link[@type='boardgamecategory']")]
        mechanisms = [lnk.get("value") for lnk in item.findall("link[@type='boardgamemechanic']")]

        # 圖片
        thumb_node = item.find("thumbnail")
        image_node = item.find("image")
        thumbnail = thumb_node.text if thumb_node is not None else None
        image = image_node.text if image_node is not None else None
        image_url = image or thumbnail

        out.append(
            {
                "bgg_id": bid,
                "name": name,
                "year": year,
                # 玩家數／時間（新欄位 + 舊名字一起寫，給後面相容）
                "min_players": min_players,
                "max_players": max_players,
                "min_playtime": min_playtime,
                "max_playtime": max_playtime,
                "minplayers": min_players,
                "maxplayers": max_players,
                "minplaytime": min_playtime,
                "maxplaytime": max_playtime,
                # 評分
                "rating_bayes": rating_bayes,
                "rating_avg": rating_avg,
                "users_rated": users_rated,
                "weight": weight,
                # 類別／機制
                "categories": categories,
                "mechanisms": mechanisms,
                # 圖片
                "thumbnail": thumbnail,
                "image": image_url,
                "image_url": image_url,
            }
        )

    return out


# ------------------------------
# main
# ------------------------------
def main():
    token = load_token()
    ids = load_ids()

    all_rows: List[Dict] = []
    total_batches = (len(ids) + BATCH_SIZE - 1) // BATCH_SIZE

    with requests.Session() as s:
        for idx, start in enumerate(range(0, len(ids), BATCH_SIZE), start=1):
            batch = ids[start : start + BATCH_SIZE]
            print(f"[{idx}/{total_batches}] Fetch id={','.join(batch)}")

            xml_bytes = fetch_batch(s, token, batch)
            if xml_bytes is None:
                # 這一批失敗就算了，先不要讓整個流程掛掉
                continue

            rows = parse_xml(xml_bytes)
            all_rows.extend(rows)

            time.sleep(SLEEP_SEC)

    OUT_JSON.write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), "utf-8")
    print(f"[OK] 共寫入 {len(all_rows)} 筆 → {OUT_JSON}")


if __name__ == "__main__":
    main()

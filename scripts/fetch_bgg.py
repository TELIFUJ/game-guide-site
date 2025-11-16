#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_bgg.py — 從 BGG XML API2 抓遊戲資料（含評分＋分類／機制）

輸入：
  data/bgg_ids.txt   內含一行一個 BGG ID（可有註解與空行）

輸出：
  data/bgg_data.json  每筆結構大約是：
  {
      "bgg_id": 8,
      "name_en": "Lords of Creation",
      "year": 1983,
      "image_url": "https://cf.geekdo-images.com/...",
      "thumbnail": "https://cf.geekdo-images.com/...",
      "rating_bayes": 6.23,
      "rating_avg": 6.45,
      "users_rated": 1234,
      "weight": 2.35,
      "categories": ["Adventure", "Fantasy"],
      "mechanisms": ["Hand Management", "Dice Rolling"]
  }

注意：
- 需要 Bearer Token 才不會 401。
- Token 來源優先順序：
    1) 環境變數：BGG_ACCESS_TOKEN / BGG_TOKEN / BGG_API_TOKEN / BGG_XMLAPI2_TOKEN
    2) 檔案：data/bgg_token.txt（單行文字）
"""

import json
import os
import pathlib
import time
from typing import List, Dict

import requests
from lxml import etree

ROOT = pathlib.Path(__file__).resolve().parents[1]
IDS_TXT = ROOT / "data" / "bgg_ids.txt"
OUT = ROOT / "data" / "bgg_data.json"

API_URL = "https://boardgamegeek.com/xmlapi2/thing"
CHUNK_SIZE = 25  # 一次查 25 個 ID，比較溫柔


# ---------- 小工具 ----------

def load_token() -> str | None:
    """從環境變數或 data/bgg_token.txt 讀取 Token。"""
    for key in ("BGG_ACCESS_TOKEN", "BGG_TOKEN", "BGG_API_TOKEN", "BGG_XMLAPI2_TOKEN"):
        val = os.environ.get(key)
        if val:
            print(f"[INFO] 使用環境變數 {key} 作為 BGG Token")
            return val.strip()

    token_file = ROOT / "data" / "bgg_token.txt"
    if token_file.exists():
        txt = token_file.read_text("utf-8").strip()
        if txt:
            print("[INFO] 使用 data/bgg_token.txt 內的 BGG Token")
            return txt

    print("[WARN] 沒有找到 BGG Token，呼叫 API 很可能 401")
    return None


def load_ids() -> List[str]:
    if not IDS_TXT.exists():
        raise SystemExit(f"[ERR] 找不到 {IDS_TXT}")

    ids: List[str] = []
    for line in IDS_TXT.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ids.append(line)
    print(f"[INFO] 讀到 {len(ids)} 個 BGG ID")
    return ids


def parse_float(text: str | None):
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def parse_int(text: str | None):
    if not text:
        return None
    try:
        return int(text)
    except Exception:
        return None


def parse_chunk(xml_bytes: bytes) -> List[Dict]:
    """把一批 XML 解析成 list[dict]."""
    root = etree.fromstring(xml_bytes)
    rows: List[Dict] = []

    for item in root.findall("item"):
        bgg_id = item.get("id")
        if not bgg_id:
            continue

        # 名稱：取 primary name
        name_node = item.find("name[@type='primary']")
        name_en = name_node.get("value") if name_node is not None else None

        year = parse_int(item.findtext("yearpublished"))

        image_url = (item.findtext("image") or "").strip() or None
        thumb = (item.findtext("thumbnail") or "").strip() or None

        # 評分統計
        rating_bayes = rating_avg = users_rated = weight = None
        stats = item.find("statistics/ratings")
        if stats is not None:
            rating_bayes = parse_float(stats.findtext("bayesaverage"))
            rating_avg = parse_float(stats.findtext("average"))
            users_rated = parse_int(stats.findtext("usersrated"))
            weight = parse_float(stats.findtext("averageweight"))

        # 分類與機制
        categories = [n.get("value") for n in item.findall("link[@type='boardgamecategory']") if n.get("value")]
        mechanisms = [n.get("value") for n in item.findall("link[@type='boardgamemechanic']") if n.get("value")]

        rows.append(
            {
                "bgg_id": int(bgg_id),
                "name_en": name_en,
                "year": year,
                "image_url": image_url,
                "thumbnail": thumb,
                "rating_bayes": rating_bayes,
                "rating_avg": rating_avg,
                "users_rated": users_rated,
                "weight": weight,
                "categories": categories,
                "mechanisms": mechanisms,
            }
        )

    return rows


# ---------- 主流程 ----------

def main():
    token = load_token()
    ids = load_ids()

    session = requests.Session()
    headers = {
        "User-Agent": "game-guide-site fetch_bgg.py (personal, non-commercial)",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    all_rows: List[Dict] = []

    for i in range(0, len(ids), CHUNK_SIZE):
        batch = ids[i : i + CHUNK_SIZE]
        print(f"[{i+1}/{len(ids)}] Fetch ids={','.join(batch)}")

        params = {
            "id": ",".join(batch),
            "stats": 1,  # 要 ratings / weight
            "type": "boardgame,boardgameexpansion",
        }

        # 簡單 retry 兩次
        for attempt in range(3):
            try:
                resp = session.get(API_URL, params=params, headers=headers, timeout=40)
            except Exception as e:
                print(f"[WARN] 連線失敗（{e}），稍後重試...")
                time.sleep(3)
                continue

            if resp.status_code == 202:
                # BGG 說「還在準備」，休息一下再要
                print("[INFO] 202 Accepted，等待 3 秒後重試這一批")
                time.sleep(3)
                continue

            if resp.status_code == 401:
                print("[ERR] HTTP 401 未授權，請確認 BGG Token 是否正確／有帶到。")
                return

            if resp.status_code != 200:
                print(f"[WARN] HTTP {resp.status_code}，略過這批 ID")
                break

            # 成功
            rows = parse_chunk(resp.content)
            all_rows.extend(rows)
            break

        # 對 API 溫柔一點
        time.sleep(1.0)

    OUT.write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), "utf-8")
    print(f"[OK] 寫出 {OUT}，共 {len(all_rows)} 筆資料")


if __name__ == "__main__":
    main()

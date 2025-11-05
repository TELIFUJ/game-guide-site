#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Resolve BoardGameGeek IDs from manual.csv

- 讀取 data/manual.csv（UTF-8 with BOM 容忍）
- 依序使用：bgg_url_override → bgg_id → bgg_query 搜尋
- 產出 data/bgg_ids.json（原子寫入，未達門檻保留舊檔）
- 以環境變數客製：
    BGG_SEARCH_TYPES   (default: 'boardgame,boardgameexpansion')
    BGG_RETRY          (default: 5)
    BGG_MIN_SAVE_IDS   (default: 5)   # 若未設定，亦會讀 BGG_MIN_SAVE
    BGG_UA             (default: 'game-guide-site/ci (+repo)')
"""

import os
import csv, json, re, time, random, xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
import requests

MANUAL = Path("data/manual.csv")
OUT    = Path("data/bgg_ids.json")

# ---- 可由 CI 覆寫 ----
SEARCH_TYPES = os.getenv("BGG_SEARCH_TYPES", "boardgame,boardgameexpansion")
RETRY        = int(os.getenv("BGG_RETRY", "5"))
MIN_SAVE     = int(os.getenv("BGG_MIN_SAVE_IDS", os.getenv("BGG_MIN_SAVE", "5")))

HEADERS = {
    "User-Agent": os.getenv("BGG_UA", "game-guide-site/ci (+https://github.com/TELIFUJ/game-guide-site)"),
    "Accept": "application/xml",
    "Referer": "https://boardgamegeek.com/",
}
JLOW, JHIGH = 0.7, 1.3


def _int_or_none(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() == "none":
        return None
    try:
        return int(float(s))
    except Exception:
        return None


def _norm_name(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[ \t\n\r\-\–\—:•·\.,!\"'®™()\[\]{}]", "", s)
    return s


def _extract_id_from_url(u: str):
    if not u:
        return None
    m = re.search(r"/(\d+)(?:/|$)", u)
    return int(m.group(1)) if m else None


def _sleep_backoff(base, attempt):
    time.sleep(base * (1.7 ** (attempt - 1)) * random.uniform(JLOW, JHIGH))


def bgg_search_to_id(session: requests.Session, q: str):
    """以 BGG XMLAPI2 搜尋並回傳最合理的 id（盡量避免 202/429）"""
    if not q:
        return None
    url = f"https://boardgamegeek.com/xmlapi2/search?type={SEARCH_TYPES}&query={quote(q)}"
    for attempt in range(1, RETRY + 1):
        r = session.get(url, timeout=30)
        # 202 = queueing；401/403/429 = 限流/權限
        if r.status_code == 202:
            _sleep_backoff(1.5, attempt)
            continue
        if r.status_code in (401, 403, 429):
            _sleep_backoff(2.5, attempt)
            continue
        r.raise_for_status()
        try:
            root = ET.fromstring(r.text)
        except ET.ParseError:
            _sleep_backoff(1.0, attempt)
            continue

        target = _norm_name(q)
        best_id, best_score = None, -1
        for it in root.findall("item"):
            if it.get("type") not in ("boardgame", "boardgameexpansion"):
                continue
            pid = int(it.get("id"))
            names = [n.get("value") for n in it.findall("name") if n.get("type") == "primary"]
            # 沒主名也保留最低分候選
            if not names:
                if best_id is None:
                    best_id, best_score = pid, 0
                continue

            primary = _norm_name(names[0])

            # 完全相等 > 前綴相等 > 子序列命中
            if primary == target:
                return pid
            score = 0
            if primary.startswith(target):
                score = 2
            elif target in primary:
                score = 1

            if score > best_score:
                best_id, best_score = pid, score

        return best_id
    return None


def main():
    if not MANUAL.exists():
        OUT.write_text("[]", encoding="utf-8")
        print("No manual.csv → 0")
        return

    s = requests.Session()
    s.headers.update(HEADERS)

    rows = []
    with MANUAL.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            entry = {
                "name_zh": r.get("name_zh") or None,
                "name_en_override": r.get("name_en_override") or None,
                "alias_zh": r.get("alias_zh") or None,
                "category_zh": r.get("category_zh") or None,
                "price_msrp_twd": _int_or_none(r.get("price_msrp_twd")),
                "price_twd": _int_or_none(r.get("price_twd")),
                "used_price_twd": _int_or_none(r.get("used_price_twd")),
                "price_note": r.get("price_note") or None,
                "used_note": r.get("used_note") or None,
                "manual_override": r.get("manual_override") or None,
                "stock": _int_or_none(r.get("stock")),
                "description": r.get("description") or None,
                "image_override": (r.get("image_override") or "").strip() or None,
                "image_version_id": (r.get("image_version_id") or "").strip() or None,
                "link_override": r.get("link_override") or None,
                "bgg_url_override": r.get("bgg_url_override") or None,
            }

            # 解析來源欄位
            bid_raw = (r.get("bgg_id") or "").strip()
            q       = (r.get("bgg_query") or "").strip()
            url_ov  = (r.get("bgg_url_override") or "").strip()

            # 1) 從網址直取
            bid = _extract_id_from_url(url_ov) if url_ov else None

            # 2) 手填 bgg_id
            if not bid and bid_raw:
                try:
                    bid = int(float(bid_raw))
                except Exception:
                    bid = None

            # 3) 搜尋
            if not bid and q:
                try:
                    bid = bgg_search_to_id(s, q)
                except Exception:
                    bid = None

            if bid:
                entry["bgg_id"] = int(bid)
            if q:
                entry["bgg_query"] = q

            rows.append(entry)

    # ---- 原子寫入＋安全門檻（避免把舊檔拿掉）----
    text = json.dumps(rows, ensure_ascii=False, indent=2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".bgg_ids.tmp.json")
    tmp.write_text(text, encoding="utf-8")

    new_count = sum(1 for r in rows if r.get("bgg_id"))
    if new_count < MIN_SAVE:
        if OUT.exists():
            # 保留舊檔，不覆蓋
            tmp.unlink(missing_ok=True)
            print(f"Below threshold ({new_count}<{MIN_SAVE}) → keep existing {OUT}")
            return
        else:
            tmp.unlink(missing_ok=True)
            raise SystemExit("ABORT: no previous bgg_ids.json and current resolve below threshold.")

    tmp.replace(OUT)
    print(f"Resolved {len(rows)} entries (with ids: {new_count}) → {OUT}")


if __name__ == "__main__":
    main()

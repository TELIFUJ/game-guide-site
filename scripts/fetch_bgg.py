# scripts/fetch_bgg.py
# -*- coding: utf-8 -*-
import os, time, json, random, xml.etree.ElementTree as ET
from pathlib import Path
import requests

INPUT  = Path("data/bgg_ids.json")
OUTPUT = Path("data/bgg_data.json")

# 主要與備援端點（均 https）
PRIMARY_BASE  = "https://boardgamegeek.com/xmlapi2/thing"
FALLBACK_BASE = "https://api.geekdo.com/xmlapi2/thing"

# 可由 CI 覆寫（預設較保守）
BATCH    = int(os.getenv("BGG_BATCH", "5"))
SLEEP    = float(os.getenv("BGG_SLEEP", "3.5"))   # 批次間固定間隔
RETRY    = int(os.getenv("BGG_RETRY", "5"))       # 每個請求最大重試
MIN_SAVE = int(os.getenv("BGG_MIN_SAVE", "50"))   # 寫檔門檻

HEADERS = {
    "User-Agent": os.getenv("BGG_UA", "game-guide-site/ci (+https://github.com/TELIFUJ/game-guide-site)"),
    "Accept": "application/xml",
    "Referer": "https://boardgamegeek.com/",
}

JITTER_LOW, JITTER_HIGH = 0.7, 1.3

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
        try:
            bid=int(item.get("id"))
        except:
            continue
        name_en=None
        for n in item.findall("name"):
            if n.get("type")=="primary":
                name_en=n.get("value"); break

        def val(tag, attr="value"):
            el=item.find(tag)
            return el.get(attr) if el is not None and el.get(attr) is not None else None

        avgw=item.find("statistics/ratings/averageweight")
        weight=_num(avgw.get("value")) if avgw is not None else None

        r_avg_el   = item.find("statistics/ratings/average")
        r_bayes_el = item.find("statistics/ratings/bayesaverage")
        rating_avg   = _num(r_avg_el.get("value"))   if r_avg_el   is not None else None
        rating_bayes = _num(r_bayes_el.get("value")) if r_bayes_el is not None else None

        rank_overall = None
        ranks_el = item.find("statistics/ratings/ranks")
        if ranks_el is not None:
            for rk in ranks_el.findall("rank"):
                nm = rk.get("name") or ""
                if nm in ("boardgame", "boardgameoverall"):
                    rank_overall = _num(rk.get("value"), int)
                    break

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

def _sleep_backoff(base, attempt):
    time.sleep(base * (1.7 ** (attempt - 1)) * random.uniform(JITTER_LOW, JITTER_HIGH))

def request_xml(session, base, ids):
    # BGG 支援逗號分隔
    url = f"{base}?stats=1&versions=1&id=" + ",".join(str(i) for i in ids)
    for attempt in range(1, RETRY + 1):
        try:
            r = session.get(url, timeout=60)
            code = r.status_code

            # 202: 後端排隊，延後再取
            if code == 202:
                _sleep_backoff(2.0, attempt)
                continue

            # WAF/限流：退避重試
            if code in (401, 403, 429, 503):
                _sleep_backoff(3.0, attempt)
                continue

            r.raise_for_status()
            # 解析 XML；若站方回 HTML/error，將觸發 ParseError
            try:
                return ET.fromstring(r.text)
            except ET.ParseError:
                _sleep_backoff(2.0, attempt)
                continue

        except requests.RequestException:
            if attempt == RETRY:
                return None
            _sleep_backoff(1.5, attempt)
    return None

def fetch_with_fallback(session, ids):
    root = request_xml(session, PRIMARY_BASE, ids)
    if root is None:
        root = request_xml(session, FALLBACK_BASE, ids)
    return root

def atomic_write(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)

def main():
    if not INPUT.exists():
        print("No data/bgg_ids.json; nothing to fetch.")
        return

    base_rows = json.loads(INPUT.read_text(encoding="utf-8"))

    # fan-out：同一 bgg_id 可能對應多列
    from collections import defaultdict
    rows_by_id = defaultdict(list)
    ids_unique = []
    for r in base_rows:
        bid = r.get("bgg_id")
        if not bid:
            continue
        bid = int(bid)
        rows_by_id[bid].append(r)
        if bid not in ids_unique:
            ids_unique.append(bid)

    s = requests.Session()
    s.headers.update(HEADERS)

    results = []
    failed_ids = []

    print(f"Resolved {len(ids_unique)} unique ids; batch={BATCH}, sleep={SLEEP}s, retry={RETRY}")

    # 逐批抓
    for i in range(0, len(ids_unique), BATCH):
        chunk = ids_unique[i:i + BATCH]
        root = fetch_with_fallback(s, chunk)

        # 批次失敗 → 單筆補抓
        if root is None:
            for bid in chunk:
                root1 = fetch_with_fallback(s, [bid])
                if root1 is None:
                    failed_ids.append(bid)
                    continue
                parsed = parse_items(root1)
                bases = rows_by_id.get(bid, [{}])
                if parsed:
                    for base in bases:
                        results.append({**base, **parsed[0]})
            time.sleep(SLEEP)
            continue

        # 批次成功
        parsed = parse_items(root)
        by_id = {int(p["bgg_id"]): p for p in parsed}
        for bid in chunk:
            p = by_id.get(int(bid))
            bases = rows_by_id.get(bid, [{}])
            if p:
                for base in bases:
                    results.append({**base, **p})
            else:
                # 批次沒看到 → 單筆補抓
                root1 = fetch_with_fallback(s, [bid])
                if root1 is None:
                    failed_ids.append(bid)
                else:
                    parsed1 = parse_items(root1)
                    if parsed1:
                        for base in bases:
                            results.append({**base, **parsed1[0]})
                    else:
                        failed_ids.append(bid)

        time.sleep(SLEEP)

    # --- 寫檔守門：不足門檻不覆寫 ---
    old_exists = OUTPUT.exists()
    old_rows = []
    if old_exists:
        try:
            old_rows = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except Exception:
            old_rows = []

    if len(results) >= MIN_SAVE:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(OUTPUT, json.dumps(results, ensure_ascii=False, indent=2))
        print(f"Fetched {len(results)} entries → {OUTPUT}")
    else:
        msg = f"WARNING: fetched {len(results)} (<{MIN_SAVE}) — keep previous file ({len(old_rows)} entries)."
        print(msg)
        if not old_rows:
            raise SystemExit("ABORT: No previous data and current fetch below threshold.")

    if failed_ids:
        print(f"Failed IDs ({len(failed_ids)}): {failed_ids[:50]}{' ...' if len(failed_ids) > 50 else ''}")

if __name__ == "__main__":
    main()

# scripts/fetch_bgg.py
# -*- coding: utf-8 -*-
import os, time, json, random, xml.etree.ElementTree as ET
from pathlib import Path
import requests

INPUT  = Path("data/bgg_ids.json")
OUTPUT = Path("data/bgg_data.json")

# --- 端點：優先使用 api.geekdo（較少觸發 WAF），可由環境變數覆寫 ---
PRIMARY_HOST = os.getenv("BGG_PRIMARY_HOST", "api").lower()   # "api" 或 "www"
if PRIMARY_HOST == "www":
    PRIMARY_BASE  = "https://boardgamegeek.com/xmlapi2/thing"
    FALLBACK_BASE = "https://api.geekdo.com/xmlapi2/thing"
else:
    PRIMARY_BASE  = "https://api.geekdo.com/xmlapi2/thing"
    FALLBACK_BASE = "https://boardgamegeek.com/xmlapi2/thing"

# --- 可由 CI 覆寫 ---
BATCH     = int(os.getenv("BGG_BATCH", "6"))                 # 更保守：6
SLEEP     = float(os.getenv("BGG_SLEEP", "4.0"))             # 批次間隔（基準）
RETRY     = int(os.getenv("BGG_RETRY", "6"))                 # 重試次數
MIN_SAVE  = int(os.getenv("BGG_MIN_SAVE", "50"))             # 寫檔門檻
USE_VERS  = int(os.getenv("BGG_VERSIONS", "0"))              # 是否帶 versions=1（預設關）
JITTER    = float(os.getenv("BGG_JITTER", "0.6"))            # 退避抖動上限秒數
WARMUP    = int(os.getenv("BGG_WARMUP", "1"))                # 是否做預熱請求（預設開）

HEADERS = {
    "User-Agent": os.getenv("BGG_UA", "game-guide-site/ci (https://github.com/TELIFUJ/game-guide-site)"),
    "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://boardgamegeek.com/",
}

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

        rank_overall=None
        ranks_el=item.find("statistics/ratings/ranks")
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

        # 若未要求 versions=1，versions_el 可能不存在；給 0
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

def _cooldown(base_sleep, attempt):
    t = base_sleep * attempt + random.random()*JITTER
    time.sleep(t)

def _make_url(base, ids):
    params = ["stats=1"]
    if USE_VERS:
        params.append("versions=1")
    params.append("id=" + ",".join(str(i) for i in ids))
    return f"{base}?{'&'.join(params)}"

def request_xml(session, base, ids):
    url = _make_url(base, ids)
    for attempt in range(1, RETRY+1):
        try:
            r = session.get(url, timeout=60)
            # 202 = queueing
            if r.status_code == 202:
                _cooldown(2.0, attempt)
                continue
            # 401/403/429：WAF/限流，退火後重試（改用另一端點或單筆）
            if r.status_code in (401, 403, 429):
                _cooldown(3.0, attempt)
                continue
            r.raise_for_status()
            return ET.fromstring(r.text)
        except Exception:
            if attempt == RETRY:
                return None
            _cooldown(1.5, attempt)
    return None

def fetch_with_fallback(session, ids):
    # 先主要域名，失敗再試備援域名
    root = request_xml(session, PRIMARY_BASE, ids)
    if root is None:
        root = request_xml(session, FALLBACK_BASE, ids)
    return root

def warmup_session(session):
    if not WARMUP:
        return
    try:
        # 取首頁幫忙設 Cookie（忽略錯誤）
        session.get("https://boardgamegeek.com/", timeout=10)
    except Exception:
        pass
    try:
        session.get("https://api.geekdo.com/", timeout=10)
    except Exception:
        pass

def merge_incremental(old_rows, new_rows):
    """當本輪結果不足門檻時，做增量合併避免掉檔。以 (bgg_id, name_zh/name_en) 為 key。"""
    def key(r):
        bid = r.get("bgg_id")
        nm  = (r.get("name_zh") or r.get("name_en") or "").strip().lower()
        return (bid, nm)

    out_map = {}
    for r in old_rows:
        out_map[key(r)] = r
    for r in new_rows:
        out_map[key(r)] = r  # 覆蓋/新增
    return list(out_map.values())

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

    s = requests.Session()
    s.headers.update(HEADERS)
    warmup_session(s)

    results=[]
    failed_ids=[]

    print(f"Resolved {len(ids_unique)} unique ids; primary={PRIMARY_BASE}, batch={BATCH}, sleep={SLEEP}s, retry={RETRY}, versions={USE_VERS}")

    # 逐批抓
    for i in range(0,len(ids_unique),BATCH):
        chunk=ids_unique[i:i+BATCH]
        root = fetch_with_fallback(s, chunk)

        # 批次失敗 → 單筆補抓
        if root is None:
            print(f"Batch {chunk[:5]}... failed; fallback to single.")
            for bid in chunk:
                root1 = fetch_with_fallback(s, [bid])
                if root1 is None:
                    failed_ids.append(bid)
                    continue
                parsed = parse_items(root1)
                bases = rows_by_id.get(bid,[{}])
                if parsed:
                    for base in bases:
                        results.append({**base, **parsed[0]})
                _cooldown(SLEEP/2.0, 1)  # 單筆間也稍退避
            time.sleep(SLEEP + random.random()*JITTER)
            continue

        # 批次成功
        parsed = parse_items(root)
        by_id = {int(p["bgg_id"]): p for p in parsed}
        for bid in chunk:
            p = by_id.get(int(bid))
            bases = rows_by_id.get(bid,[{}])
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
        time.sleep(SLEEP + random.random()*JITTER)

    # --- 寫檔策略：保護線 + 增量合併 ---
    old_exists = OUTPUT.exists()
    old_rows = []
    if old_exists:
        try:
            old_rows = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except Exception:
            old_rows = []

    # 足夠多 → 直接覆蓋
    if len(results) >= MIN_SAVE:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Fetched {len(results)} entries → {OUTPUT}")
    else:
        # 不足門檻：若有舊檔，做增量合併寫回；否則中止
        if old_rows:
            merged = merge_incremental(old_rows, results)
            OUTPUT.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"WARNING: fetched {len(results)} (<{MIN_SAVE}); wrote merged file ({len(merged)} entries) to keep dataset healthy.")
        else:
            msg = f"ABORT: fetched {len(results)} (<{MIN_SAVE}) and no previous data."
            print(msg)
            raise SystemExit(msg)

    if failed_ids:
        print(f"Failed IDs ({len(failed_ids)}): {failed_ids[:50]}{' ...' if len(failed_ids)>50 else ''}")

if __name__ == "__main__":
    main()

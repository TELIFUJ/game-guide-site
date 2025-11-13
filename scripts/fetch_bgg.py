# scripts/fetch_bgg.py
import os, time, json, random
from pathlib import Path
import xml.etree.ElementTree as ET
import requests

IDS_FILE   = Path("data/bgg_ids.json")
OUT_FILE   = Path("data/bgg_data.json")
TMP_FILE   = Path("data/.bgg_data.tmp.json")

BATCH   = min(int(os.getenv("BGG_BATCH", "20")), 20)   # 批次 ≤20
SLEEP   = float(os.getenv("BGG_SLEEP", "6.0"))         # 每請求 ≥6 秒
RETRY   = int(os.getenv("BGG_RETRY", "6"))
JITTER  = float(os.getenv("BGG_JITTER", "0.8"))
VERSIONS= os.getenv("BGG_VERSIONS", "0")
HOSTS   = [h.strip() for h in os.getenv("BGG_HOSTS", "boardgamegeek.com,api.geekdo.com").split(",")]
MIN_SAVE= int(os.getenv("BGG_MIN_SAVE", "50"))

UA = os.getenv("HTTP_UA", "PlayClass-BGG-Fetch/1.0 (contact: you@example.com)")
AC_LANG = os.getenv("HTTP_ACCEPT_LANGUAGE", "en-US,en;q=0.9")
TOKEN = os.getenv("BGG_TOKEN", "").strip()

def load_ids():
    data = json.loads(IDS_FILE.read_text(encoding="utf-8"))
    ids = []
    for x in data:
        try:
            ids.append(int(x["bgg_id"] if isinstance(x, dict) else x))
        except Exception:
            pass
    return [i for i in ids if i > 0]

def parse_xml(xml_text: str):
    root = ET.fromstring(xml_text)
    out = []
    for it in root.findall("./item"):
        try:
            bid = int(it.get("id", "0") or "0")
        except:
            continue
        name_en = ""
        for nm in it.findall("./name"):
            if nm.get("type") == "primary":
                name_en = nm.get("value") or ""
                break
        image = (it.findtext("./image") or "").strip()
        thumb = (it.findtext("./thumbnail") or "").strip()
        ratings = it.find("./statistics/ratings")
        def _f(val):
            try:
                return float(val)
            except:
                return None
        weight = _f((ratings.find("averageweight").get("value")) if ratings is not None and ratings.find("averageweight") is not None else None)
        avg = _f((ratings.find("average").get("value")) if ratings is not None and ratings.find("average") is not None else None)
        bayes = _f((ratings.find("bayesaverage").get("value")) if ratings is not None and ratings.find("bayesaverage") is not None else None)
        rank = None
        if ratings is not None:
            ranks = ratings.find("ranks")
            if ranks is not None:
                for rk in ranks.findall("rank"):
                    if rk.get("id") == "1" or rk.get("name") == "boardgame":
                        rv = rk.get("value")
                        if rv not in (None, "Not Ranked", "0", "N/A"):
                            try: rank = int(rv)
                            except: pass
                        break
        cats = [l.get("value") for l in it.findall("link[@type='boardgamecategory']")]
        mechs = [l.get("value") for l in it.findall("link[@type='boardgamemechanic']")]
        versions = it.find("versions")
        versions_count = len(versions.findall("item")) if versions is not None else 0

        out.append({
            "bgg_id": bid,
            "name_en": name_en,
            "image_url": image or thumb,
            "thumb_url": thumb or image,
            "weight": weight,
            "rating_avg": avg,
            "rating_bayes": bayes,
            "rank_overall": rank,
            "categories": cats,
            "mechanics": mechs,
            "versions_count": versions_count,
        })
    return out

def get_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": AC_LANG,
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Referer": "https://boardgamegeek.com/",
    })
    if TOKEN:
        s.headers["Authorization"] = f"Bearer {TOKEN}"
    return s

def fetch_batch(session: requests.Session, ids):
    params = {
        "stats": "1",
        "versions": VERSIONS,
        "type": "boardgame,boardgameexpansion",
        "id": ",".join(str(i) for i in ids)
    }
    for host in HOSTS:
        url = f"https://{host}/xmlapi2/thing"
        last_err = None
        for k in range(RETRY):
            try:
                r = session.get(url, params=params, timeout=45)
                if r.status_code == 200 and r.text.strip():
                    return parse_xml(r.text)
                if r.status_code in (202, 401, 403, 429, 500, 502, 503, 504):
                    wait = SLEEP * (1 + random.random() * JITTER) * (1.6 ** k)
                    time.sleep(wait)
                    continue
                time.sleep(2.0)
            except Exception as e:
                last_err = e
                time.sleep(2.0)
        # 換下一個 host
    return None  # 整批失敗

def fetch_single(session: requests.Session, idv: int):
    res = fetch_batch(session, [idv])
    return res[0] if res else None

def main():
    if not IDS_FILE.exists():
        print("No data/bgg_ids.json; skip."); return
    ids = load_ids()
    session = get_session()

    # 舊檔 cache
    old = []
    if OUT_FILE.exists():
        try:
            old = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        except:
            old = []
    cache = {int(x.get("bgg_id", 0)): x for x in old if isinstance(x, dict)}

    ok = []
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i+BATCH]
        got = fetch_batch(session, chunk)
        if got is None:
            # 單筆回退
            for one in chunk:
                it = fetch_single(session, one)
                if it: ok.append(it)
        else:
            ok.extend(got)
        time.sleep(SLEEP * (1 + random.random() * JITTER))

    # 新覆蓋舊
    merged = {int(x.get("bgg_id", 0)): x for x in ok if isinstance(x, dict)}
    merged.update(cache)
    final = list(merged.values())

    TMP_FILE.parent.mkdir(parents=True, exist_ok=True)
    TMP_FILE.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")

    if len(ok) >= MIN_SAVE or not OUT_FILE.exists():
        TMP_FILE.replace(OUT_FILE)
        print(f"Fetched {len(ok)} new / total {len(final)} → {OUT_FILE}")
    else:
        print(f"FETCH GUARD: only {len(ok)} (<{MIN_SAVE}) new; keep previous {OUT_FILE}")

if __name__ == "__main__":
    main()

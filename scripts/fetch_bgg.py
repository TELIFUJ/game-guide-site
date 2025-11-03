# --- scripts/fetch_bgg.py ---
cat <<'PY' > scripts/fetch_bgg.py
import os, time, json, random, xml.etree.ElementTree as ET
from pathlib import Path
import requests

IDS_FILE   = Path("data/bgg_ids.json")
OUT_FILE   = Path("data/bgg_data.json")
TMP_FILE   = Path("data/.bgg_data.tmp.json")

BATCH   = int(os.getenv("BGG_BATCH", "4"))
SLEEP   = float(os.getenv("BGG_SLEEP", "6.0"))
RETRY   = int(os.getenv("BGG_RETRY", "6"))
JITTER  = float(os.getenv("BGG_JITTER", "0.7"))
VERSIONS= os.getenv("BGG_VERSIONS", "0")
HOSTS   = [h.strip() for h in os.getenv("BGG_HOSTS", "api.geekdo.com,boardgamegeek.com").split(",")]
MIN_SAVE= int(os.getenv("BGG_MIN_SAVE", "50"))

UA = os.getenv("HTTP_UA", "Mozilla/5.0 (compatible; GameGuideBot/1.0)")
AC_LANG = os.getenv("HTTP_ACCEPT_LANGUAGE", "en-US,en;q=0.9")

def load_ids():
    data = json.loads(IDS_FILE.read_text(encoding="utf-8"))
    ids = []
    for x in data:
        v = x.get("bgg_id") if isinstance(x, dict) else x
        try:
            i = int(v); 
            if i > 0: ids.append(i)
        except: pass
    return ids

def get_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "text/xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": AC_LANG,
        "Referer": "https://boardgamegeek.com/",
        "Connection": "keep-alive",
    })
    return s

def parse_xml(text: str):
    root = ET.fromstring(text)
    out = []
    for it in root.findall("./item"):
        bid = int(it.get("id", "0") or "0")
        name_en = ""
        for nm in it.findall("./name"):
            if nm.get("type") == "primary":
                name_en = nm.get("value") or ""
                break
        image = (it.findtext("./image") or "").strip()
        thumb = (it.findtext("./thumbnail") or "").strip()
        cats  = [l.get("value") for l in it.findall("link[@type='boardgamecategory']")]
        mechs = [l.get("value") for l in it.findall("link[@type='boardgamemechanic']")]
        # ratings
        ratings = it.find("statistics/ratings")
        avg = bayes = None; rank_overall = None
        def _to_float(v):
            try:
                return float(v) if v not in (None,"N/A","NaN") else None
            except: return None
        if ratings is not None:
            a = ratings.find("average"); b = ratings.find("bayesaverage")
            avg   = _to_float(a.get("value")) if a is not None else None
            bayes = _to_float(b.get("value")) if b is not None else None
            ranks = ratings.find("ranks")
            if ranks is not None:
                for rk in ranks.findall("rank"):
                    if rk.get("id")=="1" or rk.get("name")=="boardgame":
                        rv = rk.get("value")
                        if rv not in (None,"Not Ranked","0","N/A"):
                            try: rank_overall = int(rv)
                            except: pass
                        break
        out.append({
            "bgg_id": bid,
            "name_en": name_en,
            "image_url": image or thumb,
            "thumb_url": thumb or image,
            "categories": cats, "mechanics": mechs,
            "rating_avg": avg, "rating_bayes": bayes, "rank_overall": rank_overall,
        })
    return out

def fetch_batch(session, ids):
    params = {"stats":"1","versions":VERSIONS,"id":",".join(str(i) for i in ids)}
    for host in HOSTS:
        url = f"https://{host}/xmlapi2/thing"
        last = None
        for k in range(RETRY):
            try:
                r = session.get(url, params=params, timeout=45)
                if r.status_code == 200 and r.text.strip():
                    return parse_xml(r.text)
                if r.status_code in (401,403,429,503):
                    time.sleep(SLEEP * (1 + random.random()*JITTER) * (1.5**k))
                    continue
                time.sleep(2.0)
            except Exception as e:
                last = e; time.sleep(2.0)
        # 換 host 重試
    return None

def fetch_single(session, one):
    res = fetch_batch(session, [one])
    return res[0] if res else None

def main():
    if not IDS_FILE.exists():
        print("No data/bgg_ids.json; skip"); return
    ids = load_ids()
    sess = get_session()

    # 舊檔作為增量來源
    old = []
    if OUT_FILE.exists():
        try: old = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        except: old = []
    cache = {int(x.get("bgg_id",0)): x for x in old if isinstance(x,dict)}

    ok = []
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i+BATCH]
        got = fetch_batch(sess, chunk)
        if got is None:
            for one in chunk:
                it = fetch_single(sess, one)
                if it: ok.append(it)
        else:
            ok.extend(got)
        time.sleep(SLEEP * (1 + random.random()*JITTER))

    merged = {int(x.get("bgg_id",0)): x for x in ok if isinstance(x,dict)}
    merged.update(cache)  # 新覆蓋舊
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
PY

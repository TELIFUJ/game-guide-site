# scripts/fetch_bgg.py
import os, time, json, random
from pathlib import Path
import xml.etree.ElementTree as ET
import requests

IDS_FILE   = Path("data/bgg_ids.json")
OUT_FILE   = Path("data/bgg_data.json")
TMP_FILE   = Path("data/.bgg_data.tmp.json")

BATCH   = int(os.getenv("BGG_BATCH", "4"))       # 小批次，降低觸發風險
SLEEP   = float(os.getenv("BGG_SLEEP", "6.0"))   # 每批等待秒數
RETRY   = int(os.getenv("BGG_RETRY", "6"))       # 重試次數
JITTER  = float(os.getenv("BGG_JITTER", "0.7"))  # 抖動比例
VERSIONS= os.getenv("BGG_VERSIONS", "0")         # 是否含 versions
HOSTS   = [h.strip() for h in os.getenv("BGG_HOSTS", "api.geekdo.com,boardgamegeek.com").split(",")]
MIN_SAVE= int(os.getenv("BGG_MIN_SAVE", "50"))   # 最少成功數才覆蓋輸出

UA = os.getenv("HTTP_UA", "Mozilla/5.0 (compatible; GameGuideBot/1.0; +https://example.invalid)")
AC_LANG = os.getenv("HTTP_ACCEPT_LANGUAGE", "en-US,en;q=0.9")

def load_ids():
    data = json.loads(IDS_FILE.read_text(encoding="utf-8"))
    ids = []
    for x in data:
        if isinstance(x, dict) and "bgg_id" in x:
            try: ids.append(int(x["bgg_id"]))
            except: pass
        else:
            try: ids.append(int(x))
            except: pass
    return [i for i in ids if i > 0]

def parse_xml(xml_text: str):
    root = ET.fromstring(xml_text)
    out = []
    for it in root.findall("./item"):
        bid = int(it.get("id", "0") or "0")
        name_en, name_zh = "", ""
        # 取最合適名稱
        for nm in it.findall("./name"):
            if nm.get("type") == "primary":
                name_en = nm.get("value") or ""
        # 取圖像
        image = (it.findtext("./image") or "").strip()
        thumb = (it.findtext("./thumbnail") or "").strip()
        out.append({
            "bgg_id": bid,
            "name_en": name_en,
            "name_zh": name_zh,   # 留白，後續流程/人工覆蓋
            "image": image or thumb,
            "thumb_url": thumb,
            "image_url": image,
        })
    return out

def get_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "text/xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": AC_LANG,
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Referer": "https://boardgamegeek.com/",
    })
    return s

def fetch_batch(session: requests.Session, ids):
    params = {"stats":"1","versions":VERSIONS,"id":",".join(str(i) for i in ids)}
    last_err = None
    for host in HOSTS:
        url = f"https://{host}/xmlapi2/thing"
        for k in range(RETRY):
            try:
                r = session.get(url, params=params, timeout=45)
                sc = r.status_code
                if sc == 200 and r.text.strip():
                    return parse_xml(r.text)
                # 對 401/403/429/503 做退避
                if sc in (401,403,429,503):
                    wait = SLEEP * (1 + random.random() * JITTER) * (1.5 ** k)
                    time.sleep(wait)
                    continue
                # 其他錯誤：短暫等待
                time.sleep(2.0)
            except Exception as e:
                last_err = e
                time.sleep(2.0)
        # 換下一個 host
    # 整批失敗，回 None
    return None

def fetch_single(session: requests.Session, idv: int):
    res = fetch_batch(session, [idv])
    return res[0] if res else None

def main():
    if not IDS_FILE.exists():
        print("No data/bgg_ids.json; skip."); return

    ids = load_ids()
    session = get_session()
    ok = []
    # 先載入舊檔作為增量合併來源
    old = []
    if OUT_FILE.exists():
        try: old = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        except: old = []
    cache = {int(x.get("bgg_id", 0)): x for x in old if isinstance(x, dict)}

    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i+BATCH]
        got = fetch_batch(session, chunk)
        if got is None:
            # 單筆回退，盡量撈回
            for one in chunk:
                it = fetch_single(session, one)
                if it: ok.append(it)
        else:
            ok.extend(got)

        # 批次間隔（含抖動）
        time.sleep(SLEEP * (1 + random.random() * JITTER))

    # 合併舊資料（新覆蓋舊）
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

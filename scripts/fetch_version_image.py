# scripts/fetch_version_image.py
import json, time, requests, xml.etree.ElementTree as ET
from pathlib import Path

INOUT = Path("data/bgg_data.json")
CACHE = Path("data/version_image_cache.json")
API = "https://boardgamegeek.com/xmlapi2/thing?type=boardgameversion&id="

def load_cache():
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

def fetch_version_image(vid:int, session:requests.Session, max_retries=6):
    cache = fetch_version_image._cache
    key = str(vid)
    if key in cache:
        return cache[key]  # 可能是 None；也直接回傳以避免重打

    url = API + key
    backoff = 2
    for _ in range(max_retries):
        r = session.get(url, timeout=60)
        if r.status_code == 202:
            time.sleep(2)
            continue
        if r.status_code == 429:
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue
        try:
            r.raise_for_status()
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue

        try:
            root = ET.fromstring(r.text)
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue

        it = root.find("item")
        if it is None:
            cache[key] = None; save_cache(cache); return None
        img = it.find("image"); thumb = it.find("thumbnail")
        out = (img.text if img is not None else None) or (thumb.text if thumb is not None else None)
        cache[key] = out
        save_cache(cache)
        return out

    cache[key] = None
    save_cache(cache)
    return None

fetch_version_image._cache = load_cache()

def main():
    if not INOUT.exists():
        print("No data/bgg_data.json; skip."); return

    rows = json.loads(INOUT.read_text(encoding="utf-8"))
    changed = False
    sess = requests.Session()

    for r in rows:
        # 有 image_override → 最高優先（不要覆蓋）
        if r.get("image_override"):
            continue

        raw = r.get("image_version_id")
        v = (raw or "").strip() if isinstance(raw, str) else (str(raw).strip() if raw is not None else "")
        if not v:
            continue
        try:
            vid = int(v)
        except:
            print(f"Skip invalid image_version_id: {v}")
            continue

        url = fetch_version_image(vid, sess)
        if url:
            r["image_url"] = url
            r["image_version_used"] = vid
            changed = True
            print(f"Using version {vid} image for bgg_id={r.get('bgg_id')}")
        else:
            print(f"No image for version {vid}")

        # 禮貌性延遲，避免過快
        time.sleep(0.6)

    if changed:
        INOUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print("fetch_version_image: updated data/bgg_data.json")
    else:
        print("fetch_version_image: no change")

if __name__ == "__main__":
    main()

# scripts/resolve_bgg.py
import csv, json, requests, xml.etree.ElementTree as ET
from pathlib import Path

MANUAL = Path("data/manual.csv")
OUT    = Path("data/bgg_ids.json")

def _int_or_none(x):
    if x is None: return None
    s = str(x).strip()
    if s == "" or s.lower() == "none": return None
    try: return int(float(s))
    except: return None

def bgg_search_to_id(q: str):
    url = f"https://boardgamegeek.com/xmlapi2/search?type=boardgame&query={requests.utils.quote(q)}"
    r = requests.get(url, timeout=30)
    while r.status_code == 202:
        r = requests.get(url, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    best = None
    for it in root.findall("item"):
        if it.get("type") != "boardgame":
            continue
        names = [n.get("value") for n in it.findall("name") if n.get("type") == "primary"]
        if names and names[0].lower() == q.lower():
            return int(it.get("id"))
        if best is None:
            best = int(it.get("id"))
    return best

def main():
    rows = []
    if not MANUAL.exists():
        OUT.write_text("[]", encoding="utf-8")
        print("No manual.csv → 0"); return

    with MANUAL.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            entry = {
                # 直接往下傳遞的手動欄位（fetch_bgg 會再與 BGG 資料 merge）
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
            bid = (r.get("bgg_id") or "").strip()
            q   = (r.get("bgg_query") or "").strip()

            if not bid and q:
                try:
                    bid = bgg_search_to_id(q)
                except Exception:
                    bid = None
            if bid:
                try:
                    entry["bgg_id"] = int(bid)
                except:
                    pass
            if q:
                entry["bgg_query"] = q

            rows.append(entry)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Resolved {len(rows)} entries → {OUT}")

if __name__ == "__main__":
    main()

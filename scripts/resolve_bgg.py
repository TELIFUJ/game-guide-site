# scripts/resolve_bgg.py
import csv, json, requests, xml.etree.ElementTree as ET
from pathlib import Path

MANUAL = Path("data/manual.csv")
OUT    = Path("data/bgg_ids.json")

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

    with MANUAL.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            entry = {
                k: r.get(k) for k in [
                    "name_zh","name_en_override","alias_zh","category_zh",
                    "price_msrp_twd","price_twd","used_price_twd",
                    "price_note","used_note","manual_override",
                    "stock","description","image_override"
                ]
            }
            bid = (r.get("bgg_id") or "").strip()
            q   = (r.get("bgg_query") or "").strip()
            if not bid and q:
                try:
                    bid = bgg_search_to_id(q)
                except Exception:
                    bid = None
            if bid:
                entry["bgg_id"] = int(bid)
            if q:
                entry["bgg_query"] = q
            rows.append(entry)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Resolved {len(rows)} entries → {OUT}")

if __name__ == "__main__":
    main()

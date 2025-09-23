# scripts/build_json.py
import json, datetime, hashlib
from pathlib import Path

INPUT  = Path("data/bgg_data.json")
OUTPUT = Path("data/games_full.json")

def slugify(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "_")

if not INPUT.exists():
    print("No data/bgg_data.json; skip build_json."); raise SystemExit(0)

rows   = json.loads(INPUT.read_text(encoding="utf-8"))
items  = []
today  = datetime.date.today().isoformat()

# 穩定 id：name / version / override / bgg_id
def make_item_id(name_en, name_zh, bid, r):
    base = slugify(name_en or name_zh or (f"bgg_{bid}" if bid else "game"))
    ver  = r.get("image_version_id") or r.get("image_version_used")
    if ver:
        return f"{base}-v{str(ver).strip()}"
    if r.get("image_override"):
        suffix = hashlib.md5(str(r["image_override"]).encode("utf-8")).hexdigest()[:8]
        return f"{base}-{suffix}"
    if bid:
        return f"{base}-{bid}"
    return base

_seen = {}  # {item_id: {"sigs": set(), "dup": 1}}
def ensure_unique(item_id: str, signature: tuple) -> str:
    bucket = _seen.setdefault(item_id, {"sigs": set(), "dup": 1})
    if signature in bucket["sigs"]:
        bucket["dup"] += 1
        return f"{item_id}-{bucket['dup']}"
    else:
        bucket["sigs"].add(signature)
        return item_id

for r in rows:
    bid     = r.get("bgg_id")
    name_en = r.get("name_en_override") or r.get("name_en") or r.get("bgg_query")
    name_zh = r.get("name_zh")

    # 圖片優先序：override > version圖(已被 fetch_version_image 寫入 image_url) > bgg原圖
    image_src = r.get("image_override") or r.get("image_url") or r.get("thumb_url")

    base_id  = make_item_id(name_en, name_zh, bid, r)
    signature = (bid, r.get("image_version_id"), r.get("image_version_used"), r.get("image_override"))
    final_id = ensure_unique(base_id, signature)

    item = dict(r)
    item["id"]        = final_id
    item["name_en"]   = name_en or ""
    item["name_zh"]   = name_zh or ""
    item["image"]     = image_src
    item["updated_at"]= today

    if bid and not item.get("bgg_url"):
        item["bgg_url"] = f"https://boardgamegeek.com/boardgame/{bid}"

    if not item.get("search_keywords"):
        kws = []
        if item["name_zh"]: kws.append(f"{item['name_zh']} BGG")
        if item["name_en"]: kws.append(f"{item['name_en']} BGG")
        item["search_keywords"] = kws

    items.append(item)

items.sort(key=lambda x: (x.get("name_zh") or x.get("name_en") or "").lower())

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Built {len(items)} entries → {OUTPUT}")

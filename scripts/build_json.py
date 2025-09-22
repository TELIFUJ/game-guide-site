# scripts/build_json.py
import json, datetime, hashlib
from pathlib import Path

INPUT  = Path("data/bgg_data.json")
OUTPUT = Path("data/games_full.json")

def slugify(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "_")

if not INPUT.exists():
    print("No data/bgg_data.json; skip build_json.")
    raise SystemExit(0)

rows   = json.loads(INPUT.read_text(encoding="utf-8"))
items  = []
today  = datetime.date.today().isoformat()

# ---- 用 名稱/版本/override/bgg_id 組穩定 id ----
def make_item_id(name_en, name_zh, bid, r):
    base = slugify(name_en or name_zh or (f"bgg_{bid}" if bid else "game"))
    ver = r.get("image_version_id") or r.get("image_version_used")
    if ver:
        return f"{base}-v{str(ver).strip()}"
    if r.get("image_override"):
        suffix = hashlib.md5(r["image_override"].encode("utf-8")).hexdigest()[:8]
        return f"{base}-{suffix}"
    if bid:
        return f"{base}-{bid}"
    return base

# ---- 聰明去重：只有同條件再次出現才加 -2/-3 ----
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
    bid      = r.get("bgg_id")
    name_en  = r.get("name_en_override") or r.get("name_en") or r.get("bgg_query") or ""
    name_zh  = r.get("name_zh") or ""
    base_id  = make_item_id(name_en, name_zh, bid, r)

    signature = (
        bid,
        r.get("image_version_id"),
        r.get("image_version_used"),
        r.get("image_override"),
    )
    final_id = ensure_unique(base_id, signature)

    # 連結：CSV 覆蓋優先（link_override / bgg_url_override）
    bgg_url = (
        r.get("link_override")
        or r.get("bgg_url_override")
        or (f"https://boardgamegeek.com/boardgame/{bid}" if bid else None)
    )

    # 顯示名稱：你要英文優先
    display_name = name_en or name_zh

    image = r.get("image_override") or r.get("image_url") or r.get("thumb_url")

    item = {
        "id": final_id,
        "name_zh": name_zh,
        "name_en": name_en,
        "display_name": display_name,   # 前端用這個渲染標題
        "aliases_zh": r.get("aliases_zh", []),
        "bgg_id": bid,
        "bgg_url": bgg_url,
        "year": r.get("year"),
        "players": r.get("players"),
        "time_min": r.get("time_min"),
        "time_max": r.get("time_max"),
        "weight": r.get("weight"),
        "categories": r.get("categories") or [],
        "categories_zh": r.get("categories_zh") or [],
        "mechanics": r.get("mechanics") or [],
        "mechanics_zh": r.get("mechanics_zh") or [],
        "versions_count": r.get("versions_count", 0),
        "image": image,
        "price_msrp_twd": r.get("price_msrp_twd"),
        "price_twd": r.get("price_twd"),
        "used_price_twd": r.get("used_price_twd"),
        "price_note": r.get("price_note"),
        "used_note": r.get("used_note"),
        "stock": r.get("stock"),
        "description": r.get("description"),
        "updated_at": today,
    }

    if not item.get("search_keywords"):
        kws = []
        if name_zh: kws.append(f"{name_zh} BGG")
        if name_en: kws.append(f"{name_en} BGG")
        item["search_keywords"] = kws

    items.append(item)

items.sort(key=lambda x: (x.get("name_zh") or x.get("name_en") or "").lower())

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Built {len(items)} entries → {OUTPUT}")

# scripts/build_json.py
import json, datetime, hashlib
from pathlib import Path

INPUT  = Path("data/bgg_data.json")
OUTPUT = Path("data/games_full.json")

def slugify(s:str)->str:
    return (s or "").strip().lower().replace(" ","_")

def make_id(r)->str:
    """以名稱為基底，若有 image_override -> 用其雜湊；否則用版本 id；再不然用 bgg_id。"""
    bid  = r.get("bgg_id")
    base = slugify(r.get("name_en_override") or r.get("name_en") or r.get("name_zh") or (f"bgg_{bid}" if bid else "game"))
    if r.get("image_override"):
        return f"{base}-{hashlib.md5(r['image_override'].encode('utf-8')).hexdigest()[:8]}"
    ver = r.get("image_version_id") or r.get("image_version_used")
    if ver:
        return f"{base}-v{str(ver).strip()}"
    if bid:
        return f"{base}-{bid}"
    return base

def main():
    if not INPUT.exists():
        print("No data/bgg_data.json; skip build_json."); return

    rows  = json.loads(INPUT.read_text(encoding="utf-8"))
    items = []
    today = datetime.date.today().isoformat()

    # 用 signature 自動去掉「完全相同」的分身（差一點點就會視為不同而保留）
    seen = set()
    def signature(r):
        return (
            r.get("bgg_id"),
            r.get("name_zh") or "",
            (r.get("name_en_override") or r.get("name_en") or r.get("bgg_query") or ""),
            r.get("image_override") or r.get("image_url") or r.get("thumb_url") or "",
            r.get("price_twd") or None,
            r.get("used_price_twd") or None,
            r.get("stock") or None,
            r.get("price_note") or "",
            r.get("image_version_id") or r.get("image_version_used") or "",
        )

    for r in rows:
        sig = signature(r)
        if sig in seen:
            continue
        seen.add(sig)

        bid     = r.get("bgg_id")
        bgg_url = f"https://boardgamegeek.com/boardgame/{bid}" if bid else None

        name_zh = r.get("name_zh")
        name_en = r.get("name_en_override") or r.get("name_en") or r.get("bgg_query")

        # 圖片：CSV 的 image_override 優先
        image = r.get("image") or r.get("image_url") or r.get("thumb_url")
        if r.get("image_override"):
            image = r["image_override"]

        item = {
          "id": make_id(r),
          "name_zh": name_zh,
          "name_en": name_en,
          "aliases_zh": r.get("aliases_zh", []),

          "bgg_id": bid,
          "bgg_url": r.get("bgg_url") or bgg_url,

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

          "image": image or "",
          "price_msrp_twd": r.get("price_msrp_twd"),
          "price_twd": r.get("price_twd"),
          "used_price_twd": r.get("used_price_twd"),
          "price_note": r.get("price_note"),
          "used_note": r.get("used_note"),
          "stock": r.get("stock"),
          "description": r.get("description"),

          "search_keywords": (
              ([(f"{name_zh} BGG")] if name_zh else []) +
              ([(f"{name_en} BGG")] if name_en else [])
          ),
          "updated_at": today
        }
        items.append(item)

    items.sort(key=lambda x: (x.get("name_zh") or x.get("name_en") or "").lower())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built {len(items)} entries → {OUTPUT}")

if __name__ == "__main__":
    main()

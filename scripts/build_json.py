# scripts/build_json.py
import json, datetime, hashlib
from pathlib import Path

INPUT  = Path("data/bgg_data.json")
OUTPUT = Path("data/games_full.json")

def slugify(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "_")

def make_id(r: dict) -> str:
    """
    穩定唯一 id 規則（避免分身互踩）：
    1) 有 image_override → base-<md5(override)前8>
    2) 其次用 image_version_id / image_version_used → base-v<ver>
    3) 否則加 bgg_id → base-<bgg_id>
    4) 都沒有就用 base
    base 以 name_en_override > name_en > name_zh > bgg_<id>
    """
    bid  = r.get("bgg_id")
    base = slugify(
        r.get("name_en_override")
        or r.get("name_en")
        or r.get("name_zh")
        or (f"bgg_{bid}" if bid else "game")
    )

    ovr = r.get("image_override")
    if ovr:
        return f"{base}-{hashlib.md5(str(ovr).encode('utf-8')).hexdigest()[:8]}"

    ver = r.get("image_version_id") or r.get("image_version_used")
    if ver:
        return f"{base}-v{str(ver).strip()}"

    if bid:
        return f"{base}-{bid}"

    return base

def main():
    if not INPUT.exists():
        print("No data/bgg_data.json; skip build_json.")
        return

    rows   = json.loads(INPUT.read_text(encoding="utf-8"))
    items  = []
    today  = datetime.date.today().isoformat()

    for r in rows:
        bid     = r.get("bgg_id")
        name_zh = r.get("name_zh")
        name_en = r.get("name_en_override") or r.get("name_en") or r.get("bgg_query")

        # 圖片：CSV 的 image_override 絕對優先
        image = r.get("image") or r.get("image_url") or r.get("thumb_url")
        if r.get("image_override"):
            image = r["image_override"]

        # 建立輸出物件（保留原欄位，再補強必備鍵）
        item = dict(r)
        item["id"]       = make_id(r)
        item["name_zh"]  = name_zh or ""
        item["name_en"]  = name_en or ""
        item["image"]    = image or ""
        if bid and not item.get("bgg_url"):
            item["bgg_url"] = f"https://boardgamegeek.com/boardgame/{bid}"

        if not item.get("search_keywords"):
            kws = []
            if name_zh: kws.append(f"{name_zh} BGG")
            if name_en: kws.append(f"{name_en} BGG")
            item["search_keywords"] = kws

        item["updated_at"] = today
        items.append(item)

    # 排序：中文名 > 英文名
    items.sort(key=lambda x: (x.get("name_zh") or x.get("name_en") or "").lower())

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built {len(items)} entries → {OUTPUT}")

if __name__ == "__main__":
    main()

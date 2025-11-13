# scripts/build_json.py
import os, json, datetime, hashlib
from pathlib import Path

INPUT    = Path("data/bgg_data.json")
OUTPUT   = Path("data/games_full.json")
BACKUP   = Path("data/games_full_backup.json")
MIN_BUILD = int(os.getenv("BUILD_MIN_ITEMS", "10"))

def slugify(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "_")

def make_id(r: dict) -> str:
    bid  = r.get("bgg_id") or r.get("id")
    base = slugify(
        r.get("name_en_override")
        or r.get("name_en")
        or r.get("name")
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

def write_json(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

def restore_from_backup(reason: str):
    if BACKUP.exists():
        write_json(OUTPUT, json.loads(BACKUP.read_text(encoding="utf-8")))
        print(f"BUILD GUARD ({reason}): restored OUTPUT from backup.")
    else:
        print(f"BUILD GUARD ({reason}): no backup; keep previous or create none.")

def main():
    if not INPUT.exists():
        if OUTPUT.exists():
            print("BUILD GUARD: no bgg_data.json; keep previous games_full.json.")
            return
        restore_from_backup("no bgg_data.json")
        return

    rows = json.loads(INPUT.read_text(encoding="utf-8"))
    items = []
    today = datetime.date.today().isoformat()

    for r in rows:
        bid      = r.get("bgg_id") or r.get("id")
        name_zh  = r.get("name_zh")
        # 相容兩種來源：name_en 優先，否則用 name
        name_en  = r.get("name_en_override") or r.get("name_en") or r.get("name") or r.get("bgg_query")
        # 相容兩種來源：image / image_url / thumb_url / thumbnail
        image    = r.get("image") or r.get("image_url") or r.get("thumb_url") or r.get("thumbnail")
        if r.get("image_override"):
            image = r["image_override"]

        item = dict(r)
        item["id"]        = make_id(r)
        item["name_zh"]   = name_zh or ""
        item["name_en"]   = name_en or ""
        item["image"]     = image or ""

        # 產出 BGG 連結
        if bid and not item.get("bgg_url"):
            item["bgg_url"] = f"https://boardgamegeek.com/boardgame/{bid}"

        # 產生搜尋關鍵字（給前端 fuzzy）
        if not item.get("search_keywords"):
            kws=[]
            if name_zh: kws.append(f"{name_zh} BGG")
            if name_en: kws.append(f"{name_en} BGG")
            item["search_keywords"]=kws

        # 將 XML2 的 rating 欄位對映到前端使用的 rating_avg
        if item.get("rating_avg") is None and isinstance(item.get("rating"), (int, float)):
            item["rating_avg"] = item["rating"]

        # 方便前端顯示人數（若有 min/maxplayers）
        try:
            mp = int(r.get("minplayers") or 0)
            xp = int(r.get("maxplayers") or 0)
            if mp or xp:
                item["players"] = [mp or None, xp or None]
        except Exception:
            pass

        item["updated_at"] = today
        items.append(item)

    # 名稱排序（中文/英文）
    items.sort(key=lambda x: (x.get("name_zh") or x.get("name_en") or "").lower())

    # Build guard：過少不覆蓋，回填備份或保留舊檔
    if len(items) < MIN_BUILD:
        if OUTPUT.exists():
            print(f"BUILD GUARD: built {len(items)} (<{MIN_BUILD}); keep previous games_full.json.")
            return
        restore_from_backup(f"built {len(items)} (<{MIN_BUILD})")
        return

    write_json(OUTPUT, items)
    write_json(BACKUP, items)
    print(f"Built {len(items)} entries → {OUTPUT} (backup refreshed)")

if __name__ == "__main__":
    main()

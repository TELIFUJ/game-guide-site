# scripts/build_json.py
import json, datetime, hashlib, re
from pathlib import Path

INPUT  = Path("data/bgg_data.json")
OUTPUT = Path("data/games_full.json")

_CJK = re.compile(r"[\u4E00-\u9FFF\u3400-\u4DBF]")

def slugify(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "_")

def make_id(r: dict) -> str:
    bid  = r.get("bgg_id")
    base = slugify(r.get("name_en_override") or r.get("name_en") or r.get("name_zh") or (f"bgg_{bid}" if bid else "game"))
    ovr = r.get("image_override")
    if ovr:
        return f"{base}-{hashlib.md5(str(ovr).encode('utf-8')).hexdigest()[:8]}"
    ver = r.get("image_version_id") or r.get("image_version_used")
    if ver:
        return f"{base}-v{str(ver).strip()}"
    if bid:
        return f"{base}-{bid}"
    return base

def has_zh_name(name_zh: str, name_en: str) -> bool:
    s = (name_zh or "") + " " + (name_en or "")
    return bool(_CJK.search(s))

def main():
    if not INPUT.exists():
        print("No data/bgg_data.json; skip build_json."); return
    rows   = json.loads(INPUT.read_text(encoding="utf-8"))
    items  = []
    today  = datetime.date.today().isoformat()

    for r in rows:
        bid     = r.get("bgg_id")
        name_zh = r.get("name_zh")
        name_en = r.get("name_en_override") or r.get("name_en") or r.get("bgg_query")
        image   = r.get("image") or r.get("image_url") or r.get("thumb_url")
        if r.get("image_override"):
            image = r["image_override"]

        item = dict(r)
        item["id"] = make_id(r)
        item["name_zh"] = name_zh or ""
        item["name_en"] = name_en or ""
        item["image"]   = image or ""
        if bid and not item.get("bgg_url"):
            item["bgg_url"] = f"https://boardgamegeek.com/boardgame/{bid}"
        if not item.get("search_keywords"):
            kws=[]
            if name_zh: kws.append(f"{name_zh} BGG")
            if name_en: kws.append(f"{name_en} BGG")
            item["search_keywords"]=kws
        item["has_zh_name"] = has_zh_name(item["name_zh"], item["name_en"])
        item["updated_at"]=today
        items.append(item)

    # 保持穩定輸出：中文優先→英文，再以字母序；利於快取/差異化 PR
    def _sort_key(x):
        n = (x.get("name_zh") or x.get("name_en") or "").lower()
        # 中文優先鍵：True 排前（故使用倒序值）
        zh_key = 0 if has_zh_name(x.get("name_zh"), x.get("name_en")) else 1
        return (zh_key, n)

    items.sort(key=_sort_key)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built {len(items)} entries → {OUTPUT}")

if __name__ == "__main__":
    main()

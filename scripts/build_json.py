# scripts/build_json.py
import json, datetime, hashlib, re
from pathlib import Path

INPUT  = Path("data/bgg_data.json")
OUTPUT = Path("data/games_full.json")

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

# ==== 中文優先工具 ====
RE_CJK = re.compile(r"[\u4E00-\u9FFF]")  # CJK Unified Ideographs
RE_ZH_KEYWORDS = re.compile(r"(chinese\s*ed(?:i|t)ion|中文版|繁體|簡體|简体)", re.IGNORECASE)

def has_cjk(s: str) -> bool:
    return bool(RE_CJK.search(s or ""))

def zh_preferred_row(r: dict) -> bool:
    """名稱含中任一 CJK 或資訊欄出現中文版本關鍵詞 → 中文優先"""
    fields = [
        r.get("name_zh") or "",
        r.get("name_en_override") or r.get("name_en") or "",
        r.get("alias_zh") or "",
        r.get("category_zh") or "",
        " ".join(r.get("tags") or []) if isinstance(r.get("tags"), list) else (r.get("tags") or ""),
        r.get("edition") or "",
        r.get("description") or "",
    ]
    blob = " ".join(fields)
    return has_cjk(fields[0]) or has_cjk(fields[1]) or has_cjk(blob) or bool(RE_ZH_KEYWORDS.search(blob))

def name_key(x: dict) -> str:
    return (x.get("name_zh") or x.get("name_en") or "").lower()

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
        # 新增：中文優先旗標（前端可選用，不破壞相容）
        item["is_zh_preferred"] = zh_preferred_row(r)

        if bid and not item.get("bgg_url"):
            item["bgg_url"] = f"https://boardgamegeek.com/boardgame/{bid}"

        if not item.get("search_keywords"):
            kws=[]
            if name_zh: kws.append(f"{name_zh} BGG")
            if name_en: kws.append(f"{name_en} BGG")
            item["search_keywords"]=kws

        item["updated_at"]=today
        items.append(item)

    # 先以名稱做基礎字母排序（穩定）
    items.sort(key=name_key)

    # 再做「中文優先」穩定分區（不改兩側相對次序）
    zh_items  = [x for x in items if x.get("is_zh_preferred")]
    non_items = [x for x in items if not x.get("is_zh_preferred")]
    items = zh_items + non_items

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built {len(items)} entries → {OUTPUT}")
    print(f"  zh_preferred: {len(zh_items)} | non_zh: {len(non_items)}")

if __name__ == "__main__":
    main()

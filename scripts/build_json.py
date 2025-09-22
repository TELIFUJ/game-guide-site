import json, datetime, hashlib
from pathlib import Path

INPUT=Path("data/bgg_data.json")
OUTPUT=Path("data/games_full.json")

def slugify(s:str)->str:
    return (s or "").strip().lower().replace(" ","_")

if not INPUT.exists():
    print("No data/bgg_data.json; skip build_json."); raise SystemExit(0)

rows=json.loads(INPUT.read_text(encoding="utf-8"))
items=[]; today=datetime.date.today().isoformat()

# NEW: 以名稱/版本/override/bgg_id 組穩定 id（可重建）
def make_item_id(name_en, name_zh, bid, r):
    base = slugify(name_en or name_zh or (f"bgg_{bid}" if bid else "game"))
    # 版本優先（支援 image_version_id 或 image_version_used）
    ver = r.get("image_version_id") or r.get("image_version_used")
    if ver:
        return f"{base}-v{str(ver).strip()}"
    # 其次使用 override 的短哈希，避免 url 太長
    if r.get("image_override"):
        suffix = hashlib.md5(r["image_override"].encode("utf-8")).hexdigest()[:8]
        return f"{base}-{suffix}"
    # 再其次用 bgg_id 強化唯一性
    if bid:
        return f"{base}-{bid}"
    # 最後回退 base
    return base

# NEW: 追蹤已使用 id，僅在「完全相同條件」也重複時才加尾碼防撞
seen = {}

def ensure_unique(item_id:str)->str:
    c = seen.get(item_id, 0)
    if c == 0:
        seen[item_id] = 1
        return item_id
    else:
        c += 1
        seen[item_id] = c
        r

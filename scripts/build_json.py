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

# ---- 規則：用 名稱/版本/override/bgg_id 組出穩定且唯一的 id ----
def make_item_id(name_en, name_zh, bid, r):
    base = slugify(name_en or name_zh or (f"bgg_{bid}" if bid else "game"))
    # 1) 最優先：版本（支援 image_version_id / image_version_used）
    ver = r.get("image_version_id") or r.get("image_version_used")
    if ver:
        return f"{base}-v{str(ver).strip()}"
    # 2) 其次：image_override → 取 URL 的 md5 前 8 碼
    if r.get("image_override"):
        suffix = hashlib.md5(r["image_override"].encode("utf-8")).hexdigest()[:8]
        return f"{base}-{suffix}"
    # 3) 再其次：bgg_id
    if bid:
        return f"{base}-{bid}"
    # 4) 最後：單純 base
    return base

# ---- 聰明去重：只有「完全相同條件」再出現時才加 -2、-3... ----
# 讓不同版本/不同 override/不同 bgg_id 的同名遊戲，各自拿到不同 id（避免前端撞 key）
_seen = {}  # {item_id: {"sigs": set(), "dup": 1}}

def ensure_unique(item_id: str, signature: tuple) -> str:
    bucket = _seen.setdefault(item_id, {"sigs": set(), "dup": 1})
    if signature in bucket["sigs"]:
        bucket["dup"] += 1
        return f"{item_id}-{bucket['dup']}"  # 第二筆同條件 → -2
    else:
        bucket["sigs"].add(signature)
        return item_id

# ---- 產生輸出 ----
for r in rows:
    bid      = r.get("bgg_id")
    name_en  = r.get("name_en") or r.get("name")  # 有些來源用 name
    name_zh  = r.get("name_zh")
    base_id  = make_item_id(name_en, name_zh, bid, r)

    # 這些欄位代表一筆資料和另一筆「是否同條件」
    signature = (
        bid,
        r.get("image_version_id"),
        r.get("image_version_used"),
        r.get("image_override"),
    )
    final_id = ensure_unique(base_id, signature)

    item = dict(r)  # 保留 resolve_bgg.py 已經整理好的欄位（分類/機制/價格…）
    item["id"] = final_id
    # 保底欄位：避免前端顯示空字串
    item["name_en"] = name_en or ""
    item["name_zh"] = name_zh or ""
    # 更新時間
    item["updated_at"] = today

    items.append(item)

# 你也可以排序一下（非必要）
items.sort(key=lambda x: (x.get("name_zh") or x.get("name_en") or "").lower())

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Built {len(items)} entries → {OUTPUT}")

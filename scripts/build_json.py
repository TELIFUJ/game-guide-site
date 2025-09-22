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

rows = json.loads(INPUT.read_text(encoding="utf-8"))
items = []
today = datetime.date.today().isoformat()

# ------------ 產生穩定 ID：名稱/版本/override/BGG_ID -------------
def make_item_id(name_en, name_zh, bid, r):
    base = slugify(name_en or name_zh or (f"bgg_{bid}" if bid else "game"))
    # 1) 有版本就用版本（支援 image_version_id 或 image_version_used）
    ver = r.get("image_version_id") or r.get("image_version_used")
    if ver:
        return f"{base}-v{str(ver).strip()}"
    # 2) 有 override 就用 URL 的 MD5 短雜湊，避免 ID 太長
    if r.get("image_override"):
        suffix = hashlib.md5(r["image_override"].encode("utf-8")).hexdigest()[:8]
        return f"{base}-{suffix}"
    # 3) 退而求其次用 bgg_id 強化唯一性
    if bid:
        return f"{base}-{bid}"
    # 4) 最後回退 base
    return base

# ------------ 只在「完全相同條件」重複時，才加尾碼避免衝突 -------------
# 結構：{item_id: {"sigs": set(), "dup": 1}}
_seen = {}

def ensure_unique(item_id: str, signature: tuple) -> str:
    bucket = _seen.setdefault(item_id, {"sigs": set(), "dup": 1})
    if signature in bucket["sigs"]:
        bucket["dup"] += 1
        return f"{item_id}-{bucket['dup']}"  # 第二筆相同條件 → -2，依此類推
    else:
        bucket["sigs"].add(signature)
        return item_id

# ---------------------------- 主迴圈 -----------------------------
for r in rows:
    name_en = r.get("name_en")
    name_zh = r.get("name_zh")
    bid     = r.get("bgg_id")

    # 先做「穩定 id」
    iid = make_item_id(name_en, name_zh, bid, r)

    # 用會影響卡片呈現/價格/庫存/名稱的關鍵欄位，建立簽章
    sig = (
        r.get("image_version_id") or r.get("image_version_used"),
        r.get("image_override"),
        r.get("price_twd"),
        r.get("used_price_twd"),
        r.get("stock"),
        slugify(name_zh or name_en),
    )

    # 若相同條件再次出現才會加尾碼
    iid = ensure_unique(iid, sig)

    # 輸出物件：沿用原本欄位，再補 id / updated_at
    item = dict(r)
    item["id"] = iid
    item["updated_at"] = today

    items.append(item)

# 保持輸出穩定（依 id 排序）
items.sort(key=lambda x: x.get("id", ""))

OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Built {len(items)} entries → {OUTPUT}")

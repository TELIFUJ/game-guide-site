import csv, json, datetime, hashlib
from pathlib import Path
from copy import deepcopy

INPUT = Path("data/bgg_data.json")
MANUAL = Path("data/manual.csv")
OUTPUT = Path("data/games_full.json")

def slugify(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "_")

if not INPUT.exists():
    print("No data/bgg_data.json; skip build_json.")
    raise SystemExit(0)

today = datetime.date.today().isoformat()

# ---------- helpers ----------
def make_item_id(name_en, name_zh, bid, r):
    """
    以 名稱/版本/override/bgg_id 組穩定 id（可重建）
    同一 bgg_id 可因不同 version/override 拆成多張卡
    """
    base = slugify(name_en or name_zh or (f"bgg_{bid}" if bid else "game"))
    ver = (r.get("image_version_id") or r.get("image_version_used"))
    if ver:
        return f"{base}-v{str(ver).strip()}"
    if r.get("image_override"):
        suffix = hashlib.md5(r["image_override"].encode("utf-8")).hexdigest()[:8]
        return f"{base}-{suffix}"
    if bid:
        return f"{base}-{bid}"
    return base

_seen_ids = {}

def ensure_unique(item_id: str) -> str:
    c = _seen_ids.get(item_id, 0)
    if c == 0:
        _seen_ids[item_id] = 1
        return item_id
    else:
        c += 1
        _seen_ids[item_id] = c
        return f"{item_id}-{c}"

def apply_manual_overrides(base: dict, mrow: dict) -> dict:
    """
    把 manual 欄位（若有值）覆蓋到 base 上。
    保留未知欄位：只要 manual.csv 有，就帶到輸出，方便前端使用。
    """
    out = deepcopy(base)
    for k, v in mrow.items():
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        # bgg_id 不要覆蓋
        if k == "bgg_id":
            continue
        out[k] = v
    return out

def read_manual_csv(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            # 正規化 bgg_id（可能為空）
            bid = (r.get("bgg_id") or "").strip()
            r["bgg_id"] = int(bid) if bid.isdigit() else None
            rows.append(r)
        return rows

# ---------- load data ----------
bgg_rows = json.loads(INPUT.read_text(encoding="utf-8"))
# 以 bgg_id 做 base 快取（base 只存一份，不代表輸出唯一）
base_by_bid = {}
for r in bgg_rows:
    bid = r.get("bgg_id")
    if bid is not None:
        base_by_bid[int(bid)] = r

manual_rows = read_manual_csv(MANUAL)
manual_group = {}
manual_no_bid = []

for r in manual_rows:
    bid = r.get("bgg_id")
    if bid:
        manual_group.setdefault(bid, []).append(r)
    else:
        manual_no_bid.append(r)

# ---------- build items ----------
items = []

# 1) 先處理有 bgg_id 的：若 manual 有多筆 → 多張卡；沒有 manual → 用 base 生成一張卡
for bid, base in base_by_bid.items():
    mlist = manual_group.get(bid)
    if mlist:
        for m in mlist:
            # 以 manual 覆蓋 base 形成一個變體
            item = apply_manual_overrides(base, m)
            # 名稱優先取 manual 的 name_zh（若有）
            name_zh = m.get("name_zh") or base.get("name_zh")
            item_id = make_item_id(base.get("name_en"), name_zh, bid, m)
            item["id"] = ensure_unique(item_id)
            item["updated_at"] = today
            items.append(item)
    else:
        # 沒有 manual，直接輸出 base 一張
        item = deepcopy(base)
        item["id"] = ensure_unique(make_item_id(item.get("name_en"), item.get("name_zh"), bid, {}))
        item["updated_at"] = today
        items.append(item)

# 2) manual 裡沒有 bgg_id 的（純手動項目），也產生卡
for m in manual_no_bid:
    # 這種沒有 base，只用 manual 自帶資訊
    bid = None
    name_zh = m.get("name_zh")
    name_en = m.get("name_en")
    item = {k: v for k, v in m.items() if v not in (None, "", [])}
    item["id"] = ensure_unique(make_item_id(name_en, name_zh, bid, m))
    item["updated_at"] = today
    items.append(item)

# ---------- write ----------
OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Built {len(items)} entries → {OUTPUT}")

# scripts/publish_games.py
import json, pathlib, glob

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE = ROOT / "site" / "data"
IMG_DIR = ROOT / "assets" / "img"

INP = DATA / "bgg_data.json"
OUT = SITE / "games.json"

rows = json.loads(INP.read_text(encoding="utf-8")) if INP.exists() else []
SITE.parent.mkdir(parents=True, exist_ok=True)

# 允許以下本地命名：
# 1) image_override 指向本地相對路徑（非 http）
# 2) 以 bgg_id 命名（12345.jpg / 12345.png / 12345.webp ...）
# 3) 以 bgg_id 作為前綴（12345-xxxx.jpg / 12345_anything.jpeg ...）
def local_image_path(r):
    ov = (r.get("image_override") or "").strip()
    if ov and not ov.lower().startswith(("http://", "https://")):
        p = IMG_DIR / ov
        if p.exists():
            return f"assets/img/{ov}"

    bid = r.get("bgg_id") or r.get("id")
    if not bid:
        return None
    # 完整比對：12345.*
    for p in IMG_DIR.glob(f"{bid}.*"):
        if p.is_file():
            return f"assets/img/{p.name}"
    # 前綴比對：12345-*.*
    for p in IMG_DIR.glob(f"{bid}-*.*"):
        if p.is_file():
            return f"assets/img/{p.name}"
    return None

out = []
normalized = 0
missing = 0

for r in rows:
    if not isinstance(r, dict):
        continue

    img_local = local_image_path(r)
    img_remote = (
        r.get("image")
        or r.get("image_url")
        or r.get("thumbnail")
        or r.get("thumb_url")
        or ""
    )

    display_image = img_local or img_remote
    if img_local:
        normalized += 1
    if not display_image:
        missing += 1

    item = {
        "id": r.get("bgg_id") or r.get("id"),
        "name": r.get("name"),
        "name_zh": r.get("name_zh"),
        "year": r.get("year"),
        "minplayers": r.get("minplayers") or r.get("min_players"),
        "maxplayers": r.get("maxplayers") or r.get("max_players"),
        "minplaytime": r.get("minplaytime") or r.get("min_playtime"),
        "maxplaytime": r.get("maxplaytime") or r.get("max_playtime"),
        "weight": r.get("weight"),
        "rating": r.get("rating") or r.get("rating_avg"),
        "rating_bayes": r.get("rating_bayes"),
        "users_rated": r.get("usersrated") or r.get("users_rated"),

        # 中文主欄位，英文備份
        "categories": r.get("categories"),
        "categories_en": r.get("categories_en"),
        "mechanisms": r.get("mechanisms"),
        "mechanisms_en": r.get("mechanisms_en"),

        # 價格
        "price": r.get("price"),
        "price_used": r.get("price_used"),

        # 圖片
        "image": display_image,
    }
    out.append(item)

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(
    f"publish_games: total={len(out)} ; normalized={normalized} ; missing_image={missing}\n"
    f"wrote → {OUT}"
)

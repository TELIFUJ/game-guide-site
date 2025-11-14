# scripts/publish_games.py
import json, pathlib, mimetypes, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE = ROOT / "site" / "data"
IMG_DIR = ROOT / "assets" / "img"

INP = DATA / "bgg_data.json"
OUT = SITE / "games.json"

rows = json.loads(INP.read_text(encoding="utf-8")) if INP.exists() else []
SITE.parent.mkdir(parents=True, exist_ok=True)

def local_image_path(r):
    # 1) 指定覆寫檔名
    ov = (r.get("image_override") or "").strip()
    if ov and not ov.lower().startswith(("http://","https://")):
        p = IMG_DIR / ov
        return f"assets/img/{ov}" if p.exists() else None
    # 2) 以 bgg_id 命名的檔案（常見）
    bid = r.get("bgg_id") or r.get("id")
    for ext in (".jpg",".jpeg",".png",".webp"):
        p = IMG_DIR / f"{bid}{ext}"
        if p.exists(): return f"assets/img/{bid}{ext}"
    # 3) 若覆寫是 URL → 不視為本地
    return None

out = []
normalized = 0; missing = 0
for r in rows:
    if not isinstance(r, dict): 
        continue
    img = local_image_path(r)
    remote = r.get("image") or r.get("image_url") or r.get("thumbnail") or r.get("thumb_url")
    if img:
        normalized += 1
        display_image = img
    elif remote:
        display_image = remote
    else:
        display_image = ""
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
        # 直接輸出中文；英文保留到 *_en 以供 CSV/搜尋
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
print(f"publish_games: total={len(out)} ; normalized={normalized} ; missing_image={missing}\n"
      f"wrote → {OUT}")

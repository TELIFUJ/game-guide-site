# scripts/publish_games.py
from __future__ import annotations
import json, pathlib

# 兼容在不同工作目錄下的 import
try:
    from scripts.common_image import normalize_bgg_image_url
except ImportError:  # fallback：若以 scripts/ 內為工作目錄執行
    from common_image import normalize_bgg_image_url

ROOT = pathlib.Path(__file__).resolve().parents[1]
src  = ROOT / "data" / "games_full.json"
dst  = ROOT / "site" / "data" / "games.json"
dst.parent.mkdir(parents=True, exist_ok=True)

data = json.loads(src.read_text(encoding="utf-8"))
fixed, missing = 0, 0

for item in data:
    # 1) 候選圖源（不改欄位命名）
    cand = item.get("image_override") or item.get("image") or item.get("thumbnail")

    # 2) 把 __imagepage 轉成可顯示圖片；也順手把 900x600 降為 400x300
    norm = normalize_bgg_image_url(cand)

    # 3) 回填到 image_override（不改規格）
    if norm:
        if norm != item.get("image_override"):
            fixed += 1
        item["image_override"] = norm
    else:
        missing += 1

# 4) 輸出前端現用檔
dst.write_text(json.dumps(data, ensure_ascii=False, separators=(",",":")), encoding="utf-8")

print(f"publish_games: total={len(data)} ; normalized={fixed} ; missing_image={missing}")
print(f"wrote -> {dst}")

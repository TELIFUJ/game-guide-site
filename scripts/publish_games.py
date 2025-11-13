# scripts/publish_games.py
from __future__ import annotations
import json, pathlib
from scripts.common_image import normalize_bgg_image_url

ROOT = pathlib.Path(__file__).resolve().parents[1]
src  = ROOT / "data" / "games_full.json"
dst  = ROOT / "site" / "data" / "games.json"
dst.parent.mkdir(parents=True, exist_ok=True)

data = json.loads(src.read_text(encoding="utf-8")) if src.exists() else []
fixed, missing = 0, 0

for item in data:
    # 三層候選：override → image → thumbnail
    cand = item.get("image_override") or item.get("image") or item.get("thumbnail")
    norm = normalize_bgg_image_url(cand)

    if norm:
        if norm != item.get("image_override"):
            fixed += 1
        # 不改規格：覆寫回 image_override
        item["image_override"] = norm
    else:
        missing += 1

dst.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"publish_games: total={len(data)} ; normalized={fixed} ; missing_image={missing}")
print(f"wrote → {dst}")

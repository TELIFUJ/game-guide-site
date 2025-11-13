from __future__ import annotations
import json, pathlib

# ---- robust import of normalize_bgg_image_url ----
try:
    from scripts.common_image import normalize_bgg_image_url
except ModuleNotFoundError:
    try:
        from common_image import normalize_bgg_image_url
    except ModuleNotFoundError:
        import sys
        sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
        from scripts.common_image import normalize_bgg_image_url

ROOT = pathlib.Path(__file__).resolve().parents[1]
src_full = ROOT / "data" / "games_full.json"
src_raw  = ROOT / "data" / "bgg_data.json"
dst      = ROOT / "site" / "data" / "games.json"
dst.parent.mkdir(parents=True, exist_ok=True)

def load_json(p: pathlib.Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

data = load_json(src_full)
if not data:
    data = load_json(src_raw)

fixed = 0
missing = 0
for item in data:
    cand = item.get("image_override") or item.get("image") or item.get("thumbnail")
    norm = normalize_bgg_image_url(cand)
    if norm:
        if norm != item.get("image_override"):
            fixed += 1
        item["image_override"] = norm
    else:
        missing += 1

dst.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"publish_games: total={len(data)} ; normalized={fixed} ; missing_image={missing}")
print(f"wrote → {dst}")

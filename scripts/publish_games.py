from __future__ import annotations
import json, pathlib

# --- robust import ---
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
SRC_FULL = ROOT / "data" / "games_full.json"
SRC_RAW  = ROOT / "data" / "bgg_data.json"
DST      = ROOT / "site" / "data" / "games.json"
DST.parent.mkdir(parents=True, exist_ok=True)

def _load_json(p: pathlib.Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

def _pick_normalized_image(item: dict) -> str:
    """
    依序嘗試三層來源：image_override → image → thumbnail
    每一層先做 normalize，若獲得可用網址即返回；否則試下一層。
    """
    for key in ("image_override", "image", "thumbnail"):
        cand = item.get(key)
        norm = normalize_bgg_image_url(cand)
        if norm:
            return norm
    return ""  # 都不可用，回傳空字串

def main():
    data = _load_json(SRC_FULL)
    if not data:
        data = _load_json(SRC_RAW)

    fixed = 0
    missing = 0

    for item in data:
        norm = _pick_normalized_image(item)
        if norm:
            if norm != item.get("image_override"):
                fixed += 1
            # 不改欄位規格，覆蓋到 image_override 給前端統一使用
            item["image_override"] = norm
        else:
            missing += 1

    DST.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )
    print(f"publish_games: total={len(data)} ; normalized={fixed} ; missing_image={missing}")
    print(f"wrote → {DST}")

if __name__ == "__main__":
    main()

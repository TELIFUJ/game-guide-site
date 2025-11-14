#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_from_csv.py — 從 manual.csv 直接產生網站資料
輸出：
- data/games_full.json（完整）
- site/data/games.json（前端使用）
"""

import csv, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "manual.csv"     # ← 這裡改成你要的 manual.csv
OUT_FULL = ROOT / "data" / "games_full.json"
OUT_SITE = ROOT / "site" / "data" / "games.json"

def main():
    if not CSV_PATH.exists():
        print(f"[ERR] 找不到 CSV：{CSV_PATH}")
        return

    rows = []
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned = {}
            for k, v in row.items():
                v = v.strip() if isinstance(v, str) else v
                cleaned[k] = v if v != "" else None

            if cleaned.get("image_override"):
                cleaned["image"] = cleaned["image_override"]
            elif cleaned.get("bgg_id"):
                cleaned["image"] = f"https://cf.geekdo-images.com/{cleaned['bgg_id']}.jpg"
            else:
                cleaned["image"] = None

            rows.append(cleaned)

    OUT_FULL.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        "utf-8"
    )

    OUT_SITE.write_text(
        json.dumps(rows, ensure_ascii=False),
        "utf-8"
    )

    print(f"[OK] build_from_csv.py 完成；rows={len(rows)}")

if __name__ == "__main__":
    main()

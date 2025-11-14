#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_from_csv.py
從你的 CSV 自動萃取 BGG 主 ID → 寫入 data/bgg_ids.txt
CSV 欄位：name_zh,bgg_id,...
"""

import csv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "manual.csv"  # 你 CSV 的檔名
OUT = ROOT / "data" / "bgg_ids.txt"

def main():
    if not CSV_PATH.exists():
        print(f"[ERR] 找不到 CSV：{CSV_PATH}")
        return

    ids = set()

    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bid = row.get("bgg_id")
            if bid and bid.isdigit():
                ids.add(int(bid))

    ids = sorted(ids)

    OUT.write_text("\n".join(str(i) for i in ids), "utf-8")
    print(f"[OK] 已產生 bgg_ids.txt，共 {len(ids)} 個 BGG ID")

if __name__ == "__main__":
    main()

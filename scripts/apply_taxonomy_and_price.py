#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
將 BGG 抓回來的 data/bgg_data.json
套用 data/manual.csv 裡的價格／庫存／圖片等覆寫欄位，
再寫回 data/bgg_data.json。

說白話：這一步才是「尊重 CSV」的地方。
"""

from __future__ import annotations
import csv
import json
import pathlib
from typing import Dict, Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

BGG_JSON_IN = DATA_DIR / "bgg_data.json"
BGG_JSON_OUT = DATA_DIR / "bgg_data.json"  # 直接覆寫
MANUAL_CSV = DATA_DIR / "manual.csv"


def _parse_number(value: Any):
    """將字串轉成 int/float；空字串或 None 則回傳 None。"""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return None


def load_bgg_data():
    if not BGG_JSON_IN.exists():
        raise SystemExit(f"[ERROR] 找不到 {BGG_JSON_IN}")
    with BGG_JSON_IN.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SystemExit("[ERROR] bgg_data.json 內容不是 list")
    return data


def load_manual_overrides() -> Dict[str, Dict[str, str]]:
    """
    讀取 manual.csv，回傳 {bgg_id(str): row(dict)}。
    欄位格式（重點幾個）：
        name_zh,bgg_id,bgg_query,name_en_override,category_zh,alias_zh,
        price_msrp_twd,price_twd,used_price_twd,price_note,used_note,
        manual_override,stock,description,image_override,image_version_id,...
    """
    overrides: Dict[str, Dict[str, str]] = {}
    if not MANUAL_CSV.exists():
        print(f"[INFO] 找不到 {MANUAL_CSV}，略過覆寫。")
        return overrides

    with MANUAL_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bgg_id = (row.get("bgg_id") or "").strip()
            if not bgg_id:
                continue
            overrides[bgg_id] = row
    print(f"[INFO] manual.csv 載入 {len(overrides)} 筆覆寫資料。")
    return overrides


def apply_override(rec: Dict[str, Any], ov: Dict[str, str]) -> None:
    """把 manual.csv 的欄位貼到單一遊戲 record 上。"""

    # 文字欄位
    text_map = {
        "name_zh": "name_zh",
        "alias_zh": "alias_zh",
        "description": "description",
        "image_override": "image_override",
        "image_version_id": "image_version_id",
        "price_note": "price_note",
        "used_note": "used_note",
    }
    for src, dst in text_map.items():
        v = (ov.get(src) or "").strip()
        if v:
            rec[dst] = v

    # 英文名稱覆寫獨立處理
    name_en_override = (ov.get("name_en_override") or "").strip()
    if name_en_override:
        rec["name_en"] = name_en_override

    # 數字欄位
    for key in ["price_msrp_twd", "price_twd", "used_price_twd", "stock", "manual_override"]:
        num = _parse_number(ov.get(key))
        if num is not None:
            rec[key] = num


def main():
    bgg_rows = load_bgg_data()
    manual_overrides = load_manual_overrides()

    applied = 0
    for rec in bgg_rows:
        bid = str(rec.get("bgg_id") or "").strip()
        if not bid:
            continue
        ov = manual_overrides.get(bid)
        if not ov:
            continue
        apply_override(rec, ov)
        applied += 1

    with BGG_JSON_OUT.open("w", encoding="utf-8") as f:
        json.dump(bgg_rows, f, ensure_ascii=False, indent=2)

    print(
        f"apply_taxonomy_and_price: total={len(bgg_rows)}, "
        f"manual_rows={len(manual_overrides)}, applied={applied}"
    )
    print(f"→ 已覆寫輸出：{BGG_JSON_OUT}")


if __name__ == "__main__":
    main()

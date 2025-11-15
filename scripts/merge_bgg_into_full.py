#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_bgg_into_full.py — 評分＋圖片＋分類／機制 merge 版

用途：
- 從 data/bgg_data.json 讀取 BGG 資料
- 依 bgg_id 對應到 data/games_full.json
- 補上／更新：
    * rating_bayes
    * rating_avg
    * users_rated
    * weight
    * categories / mechanisms（只補原本是空的）
    * image（只補原本沒有的）

會先把舊的 games_full.json 備份成 data/games_full_before_merge.json
"""

import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
FULL = ROOT / "data" / "games_full.json"
BGG  = ROOT / "data" / "bgg_data.json"
BACKUP = ROOT / "data" / "games_full_before_merge.json"


def norm_id(x):
    if x is None:
        return None
    s = str(x).strip()
    return s or None


def main():
    if not FULL.exists():
        print(f"[ERR] 找不到 {FULL}")
        return
    if not BGG.exists():
        print(f"[ERR] 找不到 {BGG}")
        return

    # 備份一份舊的 games_full.json
    if not BACKUP.exists():
        shutil.copy2(FULL, BACKUP)
        print(f"[INFO] 已建立備份：{BACKUP}")
    else:
        print(f"[INFO] 已存在備份：{BACKUP}（不覆蓋）")

    full_data = json.loads(FULL.read_text("utf-8"))
    bgg_data = json.loads(BGG.read_text("utf-8"))
    print(f"[INFO] BGG 資料筆數：{len(bgg_data)}")

    # 依 bgg_id 建索引
    bgg_by_id = {}
    for r in bgg_data:
        bid = norm_id(r.get("bgg_id") or r.get("id"))
        if bid:
            bgg_by_id[bid] = r

    matched = 0
    rating_upd = 0
    img_upd = 0
    cats_mech_upd = 0

    def pick(src: dict, *keys):
        """從 src 中依序取第一個有值的 key。"""
        for k in keys:
            if k in src and src[k] not in (None, "", "-"):
                return src[k]
        return None

    for g in full_data:
        bid = norm_id(g.get("bgg_id"))
        if not bid:
            continue

        src = bgg_by_id.get(bid)
        if not src:
            continue

        matched += 1

        # ---------- 評分欄位 ----------
        before = (
            g.get("rating_bayes"),
            g.get("rating_avg"),
            g.get("users_rated"),
            g.get("weight"),
        )

        rb = pick(src, "rating_bayes", "bayes", "bayesaverage")
        ra = pick(src, "rating_avg", "rating")
        ur = pick(src, "users_rated", "usersrated")
        wt = pick(src, "weight", "weight_avg")

        if rb is not None:
            g["rating_bayes"] = rb
        if ra is not None:
            g["rating_avg"] = ra
        if ur is not None:
            g["users_rated"] = ur
        if wt is not None:
            g["weight"] = wt

        after = (
            g.get("rating_bayes"),
            g.get("rating_avg"),
            g.get("users_rated"),
            g.get("weight"),
        )
        if after != before:
            rating_upd += 1

        # ---------- 分類／機制：只補空的 ----------
        cats_src = src.get("categories") or []
        mechs_src = src.get("mechanisms") or []
        changed_cm = False

        if cats_src and not g.get("categories"):
            g["categories"] = cats_src
            changed_cm = True
        if mechs_src and not g.get("mechanisms"):
            g["mechanisms"] = mechs_src
            changed_cm = True

        if changed_cm:
            cats_mech_upd += 1

        # ---------- 圖片：只補沒有的 ----------
        if not g.get("image"):
            img = src.get("image") or src.get("thumbnail")
            if img:
                g["image"] = img
                img_upd += 1

    FULL.write_text(json.dumps(full_data, ensure_ascii=False, indent=2), "utf-8")

    print(f"[OK] merge_bgg_into_full 完成；總筆數={len(full_data)}")
    print(f"     有對到 BGG 的遊戲：{matched}")
    print(f"     評分／評分人數欄位更新：{rating_upd} 次")
    print(f"     圖片更新（含補空白）：{img_upd} 筆")
    print(f"     補上分類／機制：{cats_mech_upd} 筆")


if __name__ == "__main__":
    main()

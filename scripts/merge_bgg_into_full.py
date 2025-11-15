#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_bgg_into_full.py  —  BGG 評分＋圖片合併（完整搜尋版）

目的：
- 保留目前 games_full.json 的結構與資料為主，
  只「補上」來自 BGG 的評分、重量、年份與圖片。

來源：
- data/games_full.json  ：你現在穩定在用的主資料表
- data/bgg_data.json    ：fetch_bgg.py + normalize_bgg_data.py 產生

保護機制：
- 第一次執行會自動備份為 data/games_full_before_merge.json
- 有 image_override 的遊戲：絕對不改 image
- 只在原本為 None / "" / "-" 時才補 rating_* / users_rated / weight / year
- 圖片只會在「原本是空」或「看起來是假網址（.../117814.jpg）」時，改成 BGG 的正式 image
"""

import json
from pathlib import Path
from typing import Any, Iterable, Set

ROOT = Path(__file__).resolve().parents[1]
FULL = ROOT / "data" / "games_full.json"
BGG  = ROOT / "data" / "bgg_data.json"
BACKUP = ROOT / "data" / "games_full_before_merge.json"


# ---------- 通用工具 ----------

def read_json(path: Path):
    if not path.exists():
        raise SystemExit(f"[ERR] 找不到檔案：{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"[ERR] JSON 解析失敗：{path} → {e}")
    if not isinstance(data, list):
        raise SystemExit(f"[ERR] {path} 應該是 list[dict] 結構")
    return data


def to_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def to_int(v: Any):
    try:
        s = to_str(v)
        if not s:
            return None
        return int(float(s))
    except Exception:
        return None


def to_float(v: Any):
    try:
        s = to_str(v)
        if not s:
            return None
        if s.lower() in {"nan", "inf", "-inf"}:
            return None
        return float(s)
    except Exception:
        return None


def looks_like_placeholder_image(url: str, bgg_id: str) -> bool:
    """
    判斷是不是舊的「https://cf.geekdo-images.com/{id}.jpg」假網址。
    只有這種才會被 BGG 真實 image 覆蓋。
    """
    if not url or not bgg_id:
        return False
    s = url.strip()
    bid = str(bgg_id).strip()
    if not bid:
        return False
    return s.endswith("/" + bid + ".jpg") or s.endswith(bid + ".jpg")


def find_any_key(obj: Any, keys: Iterable[str]):
    """
    在整個 dict（包含巢狀 dict / list）裡搜尋第一個符合 key 的值。
    e.g. keys = {"bayesaverage","rating_bayes","bayes_average"}
    """
    target: Set[str] = {k for k in keys}
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k in target and v not in (None, "", []):
                    return v
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                if isinstance(v, (dict, list)):
                    stack.append(v)
    return None


# ---------- BGG 資料索引 ----------

def build_bgg_index(rows):
    """
    將 bgg_data.json 轉成 {bgg_id(str): row}。
    """
    idx = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        bid = r.get("bgg_id") or r.get("id")
        bid = to_str(bid)
        if not bid:
            # 有些腳本可能把 id 放在內層，再嘗試找一次
            inner_id = find_any_key(r, {"bgg_id", "id"})
            bid = to_str(inner_id)
        if not bid:
            continue
        if bid not in idx:
            idx[bid] = r
    return idx


def pick_bgg_fields(b: dict):
    """
    從單一 BGG row 中挑出需要的欄位。
    利用 find_any_key，在整個物件裡找對應 key。
    """
    rating_bayes = find_any_key(
        b, {"rating_bayes", "bayesaverage", "bayes_average"}
    )
    rating_avg = find_any_key(
        b, {"rating_avg", "average", "rating"}
    )
    users_rated = find_any_key(
        b, {"users_rated", "usersrated", "numvotes"}
    )
    weight = find_any_key(
        b, {"weight", "weight_avg", "avgweight", "averageweight"}
    )
    year = find_any_key(
        b, {"year", "year_published", "yearpublished"}
    )
    image = find_any_key(
        b, {"image", "image_url"}
    )
    thumb = find_any_key(
        b, {"thumbnail", "thumb"}
    )

    return {
        "rating_bayes": to_float(rating_bayes),
        "rating_avg": to_float(rating_avg),
        "users_rated": to_int(users_rated),
        "weight": to_float(weight),
        "year": to_int(year),
        "image": to_str(image) or None,
        "thumbnail": to_str(thumb) or None,
    }


# ---------- 主流程 ----------

def main():
    full_rows = read_json(FULL)
    bgg_rows = read_json(BGG)

    # 備份一次
    if not BACKUP.exists():
        BACKUP.write_text(
            json.dumps(full_rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[INFO] 已建立備份：{BACKUP}")
    else:
        print(f"[INFO] 已存在備份：{BACKUP}（不覆蓋）")

    bgg_index = build_bgg_index(bgg_rows)
    print(f"[INFO] BGG 資料筆數：{len(bgg_index)}")

    merged_count = 0
    rating_updated = 0
    image_updated = 0
    thumb_updated = 0

    for g in full_rows:
        if not isinstance(g, dict):
            continue

        bid = to_str(g.get("bgg_id"))
        if not bid:
            continue

        b = bgg_index.get(bid)
        if not b:
            continue

        merged_count += 1
        info = pick_bgg_fields(b)

        # ---- 評分／評分人數／重量／年份：只補空值 ----
        if g.get("rating_bayes") in (None, "", "-") and info["rating_bayes"] is not None:
            g["rating_bayes"] = info["rating_bayes"]
            rating_updated += 1

        if g.get("rating_avg") in (None, "", "-") and info["rating_avg"] is not None:
            g["rating_avg"] = info["rating_avg"]
            rating_updated += 1

        if g.get("users_rated") in (None, "", "-") and info["users_rated"] is not None:
            g["users_rated"] = info["users_rated"]
            rating_updated += 1

        if g.get("weight") in (None, "", "-") and info["weight"] is not None:
            g["weight"] = info["weight"]

        if g.get("year") in (None, "", "-") and info["year"] is not None:
            g["year"] = info["year"]

        # ---- 圖片：尊重 image_override，只替換假網址或空值 ----
        manual_override = bool(g.get("image_override"))
        current_image = to_str(g.get("image"))

        if not manual_override and info["image"]:
            if (not current_image) or looks_like_placeholder_image(current_image, bid):
                g["image"] = info["image"]
                image_updated += 1

        # 縮圖：只有原本沒有才補
        if not g.get("thumbnail") and info["thumbnail"]:
            g["thumbnail"] = info["thumbnail"]
            thumb_updated += 1

    # 寫回 games_full.json
    FULL.write_text(
        json.dumps(full_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[OK] merge_bgg_into_full 完成；總筆數={len(full_rows)}")
    print(f"     有對到 BGG 的遊戲：{merged_count}")
    print(f"     評分／評分人數欄位更新：{rating_updated} 次")
    print(f"     圖片更新（含替換假網址）：{image_updated} 筆")
    print(f"     補上 thumbnail：{thumb_updated} 筆")
    print("")
    print("接下來請再執行：python3 scripts/publish_games.py")


if __name__ == "__main__":
    main()

# scripts/apply_taxonomy_and_price.py
# -*- coding: utf-8 -*-

"""
把 BGG 抓回的 data/bgg_data.json 與本地的分類／價格等資料合併回寫同一檔。
- 允許多種來源與欄位名稱（寬鬆解析），檔案不存在則自動略過。
- 僅使用標準函式庫（csv/json），不依賴 pandas。
- 保留原欄位，新增或覆蓋以下常見欄位（若來源提供）：
  tags, categories, mechanisms, families, playstyle, theme,
  price_twd, msrp_twd, price_note,
  image_override / image_url_override（會寫入 image_url）
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple

# --- 安全匯入（可留著，即使目前沒用到也不會報錯） ---
try:
    from scripts.common_image import normalize_bgg_image_url  # noqa: F401
except Exception:
    # 當前執行環境若無法解析 package，退回把專案根目錄塞進 sys.path
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from scripts.common_image import normalize_bgg_image_url  # noqa: F401
    except Exception:
        normalize_bgg_image_url = lambda x: x  # 安全降級：不影響後續流程

# ---- 檔案路徑 ----
BGG_INOUT = Path("data/bgg_data.json")  # 讀入並回寫
IDS_JSON = Path("data/bgg_ids.json")  # 只用來協助 ID 校驗（若存在）

# 可選分類資料（擇一或多個存在即讀）
TAXONOMY_CANDIDATES = [
    Path("data/taxonomy.json"),
    Path("data/taxonomy_overrides.json"),
    Path("data/taxonomy.csv"),
    Path("data/taxonomy.tsv"),
    Path("data/categories.csv"),
    Path("data/categories.tsv"),
]

# 可選價格資料
PRICE_CANDIDATES = [
    Path("data/prices.json"),
    Path("data/price_overrides.json"),
    Path("data/prices.csv"),
    Path("data/prices.tsv"),
    Path("data/price.csv"),
    Path("data/price.tsv"),
]

# 額外覆蓋（任意欄位），以 bgg_id 或 name 對應
OVERRIDE_CANDIDATES = [
    Path("data/overrides.json"),
    Path("data/games_overrides.json"),
]


# ---------- 小工具 ----------

def _to_int(x: Any) -> int | None:
    try:
        if x is None or str(x).strip() == "":
            return None
        return int(float(str(x).strip()))
    except Exception:
        return None


def _to_float(x: Any) -> float | None:
    try:
        if x is None or str(x).strip() == "":
            return None
        return float(str(x).replace(",", "").strip())
    except Exception:
        return None


def _norm_name_key(s: str | None) -> str:
    return (s or "").strip().lower()


def _split_tokens(v: Any) -> List[str]:
    """
    切分字串欄位成 list（允許使用 | , / ; 全形/半形逗號）
    """
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v).replace("，", ",").replace("；", ";").strip()
    tokens = []
    for sep in ["|", ",", "/", ";"]:
        if sep in s:
            tokens = [t.strip() for t in s.split(sep)]
            break
    if not tokens:
        tokens = [s] if s else []
    return [t for t in tokens if t]


def _choose_first(*vals) -> Any:
    for v in vals:
        if v not in (None, "", []):
            return v
    return None


def _ensure_list(x: Any) -> List[Any]:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


# ---------- 載入來源檔 ----------

def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_csv_or_tsv(path: Path) -> List[Dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
        # 自動判定分隔符
        dialect = "excel"
        if path.suffix.lower() == ".tsv":
            delimiter = "\t"
        else:
            # 粗略偵測
            delimiter = "," if text.count(",") >= text.count("\t") else "\t"
        reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
        out = []
        for row in reader:
            out.append({k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()})
        return out
    except Exception:
        return []


def _load_flexible_table(paths: List[Path]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for p in paths:
        if not p.exists():
            continue
        if p.suffix.lower() in (".json",):
            data = _load_json(p)
            if isinstance(data, dict):
                # 允許 dict-of-dicts
                for k, v in data.items():
                    if isinstance(v, dict):
                        v2 = dict(v)
                        v2["_key"] = k
                        rows.append(v2)
            elif isinstance(data, list):
                rows.extend([x for x in data if isinstance(x, dict)])
        elif p.suffix.lower() in (".csv", ".tsv"):
            rows.extend(_load_csv_or_tsv(p))
    return rows


# ---------- 建索引（bgg_id / name 皆可） ----------

def _index_rows_by_id_and_name(rows: List[Dict[str, Any]]) -> Tuple[Dict[int, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    by_id: Dict[int, Dict[str, Any]] = {}
    by_name: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        # 常見欄位名容錯
        idv = _to_int(_choose_first(
            r.get("bgg_id"), r.get("id"), r.get("game_id"), r.get("bggid"), r.get("BGG_ID"), r.get("_key")
        ))
        namev = _choose_first(
            r.get("name"), r.get("title"), r.get("game_name"), r.get("Name"), r.get("名稱")
        )
        if idv is not None:
            by_id[idv] = r
        if namev:
            by_name[_norm_name_key(namev)] = r
    return by_id, by_name


# ---------- 合併規則 ----------

TAX_FIELD_ALIASES = {
    "tags": ["tags", "tag", "標籤"],
    "categories": ["categories", "category", "類別", "分類"],
    "mechanisms": ["mechanisms", "mechanic", "機制"],
    "families": ["families", "family", "系列"],
    "playstyle": ["playstyle", "style", "風格"],
    "theme": ["theme", "主題"],
    "image_override": ["image_override", "image_url_override", "image", "圖片覆蓋", "image_url"],
}

PRICE_FIELD_ALIASES = {
    "price_twd": ["price_twd", "price", "售價", "價格", "售價TWD"],
    "msrp_twd": ["msrp_twd", "msrp", "建議售價", "定價"],
    "price_note": ["price_note", "note", "備註"],
}

ID_ALIASES = ["bgg_id", "id", "game_id", "bggid", "BGG_ID"]


def _pick_first_field(row: Dict[str, Any], names: List[str]) -> Any:
    for n in names:
        if n in row and row[n] not in (None, ""):
            return row[n]
    return None


def _merge_taxonomy(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    for std, aliases in TAX_FIELD_ALIASES.items():
        raw = _pick_first_field(src, aliases)
        if raw is None:
            continue
        if std == "image_override":
            # 特殊：圖片覆蓋 → 寫入 image_url
            url = normalize_bgg_image_url(str(raw))
            if url:
                dst["image_url"] = url
                # 同時保留一個來源標記，方便後續腳本下載
                dst["_image_source"] = "override"
            continue
        vals = _split_tokens(raw)
        if not vals:
            continue
        cur = _ensure_list(dst.get(std))
        # 去重
        merged = []
        seen = set()
        for v in cur + vals:
            key = str(v).strip()
            if key and key not in seen:
                merged.append(key)
                seen.add(key)
        dst[std] = merged


def _merge_price(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    # 價格類欄位
    p = _to_float(_pick_first_field(src, PRICE_FIELD_ALIASES["price_twd"]))
    m = _to_float(_pick_first_field(src, PRICE_FIELD_ALIASES["msrp_twd"]))
    n = _pick_first_field(src, PRICE_FIELD_ALIASES["price_note"])
    if p is not None:
        dst["price_twd"] = p
    if m is not None:
        dst["msrp_twd"] = m
    if n:
        dst["price_note"] = str(n).strip()


def _merge_generic_overrides(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    """
    允許任意欄位覆蓋（price/tax 以外），但保留已知欄位的專屬邏輯。
    """
    for k, v in src.items():
        lk = k.strip().lower()
        if lk in {"", "_key"}:
            continue
        # 已由 taxonomy/price 規則處理過的跳過
        if lk in {"tags", "tag", "categories", "category", "mechanisms", "mechanic",
                  "families", "family", "playstyle", "style", "theme",
                  "image_override", "image_url_override", "image"}:
            continue
        if lk in {"price_twd", "price", "售價", "價格", "msrp_twd", "msrp", "建議售價", "定價", "price_note", "note", "備註"}:
            continue
        # 直接覆蓋
        dst[k] = v


# ---------- 主流程 ----------

def main() -> int:
    if not BGG_INOUT.exists():
        print("No data/bgg_data.json; skip.")
        return 0

    # 讀主檔
    try:
        games: List[Dict[str, Any]] = json.loads(BGG_INOUT.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Read {BGG_INOUT} failed: {e}")
        return 1

    # 建 bgg id → index
    idx_by_id: Dict[int, int] = {}
    idx_by_name: Dict[str, int] = {}
    for i, g in enumerate(games):
        gid = _to_int(g.get("bgg_id") or g.get("id"))
        if gid is not None:
            idx_by_id[gid] = i
        nm = _norm_name_key(g.get("name"))
        if nm:
            idx_by_name[nm] = i

        # 先把原始 image 也正規化一次（容錯）
        if g.get("image_url"):
            g["image_url"] = normalize_bgg_image_url(g["image_url"])
        elif g.get("image"):
            g["image_url"] = normalize_bgg_image_url(g["image"])

    # 讀 taxonomy / price / overrides
    taxonomy_rows = _load_flexible_table(TAXONOMY_CANDIDATES)
    price_rows = _load_flexible_table(PRICE_CANDIDATES)
    override_rows = _load_flexible_table(OVERRIDE_CANDIDATES)

    tax_by_id, tax_by_name = _index_rows_by_id_and_name(taxonomy_rows)
    price_by_id, price_by_name = _index_rows_by_id_and_name(price_rows)
    over_by_id, over_by_name = _index_rows_by_id_and_name(override_rows)

    # 合併
    hit_tax = hit_price = hit_over = 0
    for i, g in enumerate(games):
        gid = _to_int(g.get("bgg_id") or g.get("id"))
        nmkey = _norm_name_key(g.get("name"))

        # taxonomy
        src = tax_by_id.get(gid) if gid is not None else None
        if not src and nmkey:
            src = tax_by_name.get(nmkey)
        if src:
            _merge_taxonomy(g, src)
            hit_tax += 1

        # price
        src = price_by_id.get(gid) if gid is not None else None
        if not src and nmkey:
            src = price_by_name.get(nmkey)
        if src:
            _merge_price(g, src)
            hit_price += 1

        # generic overrides
        src = over_by_id.get(gid) if gid is not None else None
        if not src and nmkey:
            src = over_by_name.get(nmkey)
        if src:
            _merge_generic_overrides(g, src)
            hit_over += 1

        # 再次正規化 image_url（若被 overrides/tax 改過）
        if g.get("image_url"):
            g["image_url"] = normalize_bgg_image_url(g["image_url"])

        # 兼容欄位：players / time（若後面流程要用到）
        minp = _to_int(g.get("minplayers") or g.get("min_players"))
        maxp = _to_int(g.get("maxplayers") or g.get("max_players"))
        if minp and maxp:
            g.setdefault("players", f"{minp}–{maxp}")
        elif maxp:
            g.setdefault("players", f"{maxp}")
        elif minp:
            g.setdefault("players", f"{minp}")

        mint = _to_int(g.get("minplaytime") or g.get("min_playtime"))
        maxt = _to_int(g.get("maxplaytime") or g.get("max_playtime"))
        if mint and maxt:
            g.setdefault("time", f"{mint}–{maxt}")
        elif maxt:
            g.setdefault("time", f"{maxt}")
        elif mint:
            g.setdefault("time", f"{mint}")

    # 回寫
    BGG_INOUT.write_text(json.dumps(games, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Merged taxonomy({hit_tax}) price({hit_price}) overrides({hit_over}) "
        f"→ total {len(games)} → {BGG_INOUT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

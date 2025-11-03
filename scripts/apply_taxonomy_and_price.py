# scripts/apply_taxonomy_and_price.py
# -*- coding: utf-8 -*-
import csv, json, re, urllib.parse
from pathlib import Path
from typing import Optional, Iterable

BGG_IN      = Path("data/bgg_data.json")
CATMAP_CSV  = Path("data/category_map_zh.csv")
MECHMAP_CSV = Path("data/mechanism_map_zh.csv")

# ---------- helpers ----------
def load_map(csv_path: Path, key_en: str, key_zh: str) -> dict:
    m = {}
    if not csv_path.exists():
        return m
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            en = (row.get(key_en) or "").strip()
            zh = (row.get(key_zh) or "").strip()
            if en:
                m[en] = zh or en
    return m

def _dedup_keep_order(xs: Iterable[str]) -> list[str]:
    seen, out = set(), []
    for x in xs:
        if not x:
            continue
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def _parse_list_zh(s: str) -> list[str]:
    # 支援 「； / 、 ; ,」 等分隔
    if s is None:
        return []
    tmp = re.sub(r"[，/；;、]", ";", str(s))
    return [x.strip() for x in tmp.split(";") if x.strip()]

def with_cache_param(url: Optional[str], ver: Optional[str]) -> Optional[str]:
    if not url or not ver:
        return url
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qsl(u.query, keep_blank_values=True)
    if any(k.lower() == "v" for k, _ in q):
        return url
    q.append(("v", str(ver)))
    new_q = urllib.parse.urlencode(q)
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, new_q, u.fragment))

_price_re = re.compile(r"[\d,]+(?:\.\d+)?")
def _norm_price(v) -> Optional[int]:
    """
    將 'NT$1,200'、'1,200'、'1200.0' 轉成 int；空字串/None/非數字 => None
    """
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    m = _price_re.search(s)
    if not m:
        return None
    num = m.group(0).replace(",", "")
    try:
        return int(float(num))
    except Exception:
        return None

def _as_list(v) -> list:
    if isinstance(v, list):
        return v
    if v is None or v == "":
        return []
    return [v]

def _map_zh_list(en_list: list[str], mapping: dict) -> list[str]:
    norm = lambda s: re.sub(r"\s+", " ", str(s or "")).replace("\u00A0", " ").strip()
    out = [mapping.get(norm(x), norm(x)) for x in en_list if norm(x)]
    return _dedup_keep_order(out)

# ---------- main ----------
def main():
    if not BGG_IN.exists():
        print("No data/bgg_data.json; skip apply.")
        return

    catmap  = load_map(CATMAP_CSV,  "bgg_category_en",  "category_zh")
    mechmap = load_map(MECHMAP_CSV, "bgg_mechanism_en", "mechanism_zh")

    rows = json.loads(BGG_IN.read_text(encoding="utf-8"))
    out  = []

    for r in rows:
        rr = dict(r)  # 就地更新（冪等）

        # aliases_zh：兼容舊欄位 alias_zh（單字串）→ 陣列
        if rr.get("alias_zh"):
            rr["aliases_zh"] = _dedup_keep_order(_parse_list_zh(rr.get("alias_zh")))
        elif rr.get("aliases_zh"):
            rr["aliases_zh"] = _dedup_keep_order([str(x).strip() for x in rr["aliases_zh"] if str(x).strip()])

        # 只要有 image_override 就直接定案到 image，並加 v= 抗快取（與下載流程互不衝突）
        img_ovr = (rr.get("image_override") or "").strip()
        if img_ovr:
            ver = (str(rr.get("image_version_id")).strip()
                   if rr.get("image_version_id") not in (None, "") else None)
            rr["image"] = with_cache_param(img_ovr, ver)

        # ---- 中文分類：優先順序  category_zh(字串) > categories_zh(清單) > EN+映射 ----
        if rr.get("category_zh"):
            rr["categories_zh"] = _dedup_keep_order(_parse_list_zh(rr["category_zh"]))
        else:
            cz = _as_list(rr.get("categories_zh"))
            if cz:
                rr["categories_zh"] = _dedup_keep_order([str(x).strip() for x in cz if str(x).strip()])
            else:
                en = _as_list(rr.get("categories"))
                rr["categories_zh"] = _map_zh_list(en, catmap)

        # ---- 中文機制：若已有 mechanics_zh 就清理；否則用 EN+映射 ----
        mz = _as_list(rr.get("mechanics_zh"))
        if mz:
            rr["mechanics_zh"] = _dedup_keep_order([str(x).replace("\u00A0", " ").strip() for x in mz if str(x).strip()])
        else:
            me = _as_list(rr.get("mechanics"))
            rr["mechanics_zh"] = _map_zh_list(me, mechmap)

        # ---- BGG URL 補完（不覆蓋外部 override 鍵）----
        if not rr.get("bgg_url"):
            bid = rr.get("bgg_id")
            if bid:
                rr["bgg_url"] = f"https://boardgamegeek.com/boardgame/{bid}"

        # ---- 價格欄位正規化（保留空為 None）----
        for k in ("price_twd", "used_price_twd", "price_msrp_twd"):
            rr[k] = _norm_price(rr.get(k))

        # ---- 搜尋關鍵字輕量補充（不覆蓋既有）----
        kw = set()
        for s in rr.get("search_keywords", []):
            if s is not None and str(s).strip():
                kw.add(str(s).strip())
        for s in rr.get("aliases_zh", []):
            if s is not None and str(s).strip():
                kw.add(str(s).strip())
        # 注入中文分類/機制（可被 UI 模糊比對利用）
        for s in rr.get("categories_zh", []):
            if s:
                kw.add(str(s))
        for s in rr.get("mechanics_zh", []):
            if s:
                kw.add(str(s))
        if kw:
            rr["search_keywords"] = sorted(kw)

        out.append(rr)

    BGG_IN.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"apply_taxonomy_and_price: total {len(out)}; zh fields applied; prices normalized; image override respected.")

if __name__ == "__main__":
    main()

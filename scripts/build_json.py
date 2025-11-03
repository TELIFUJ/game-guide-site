# scripts/build_json.py
import json, datetime, hashlib, re
from pathlib import Path

INPUT   = Path("data/bgg_data.json")
OUTPUT  = Path("data/games_full.json")
SNAP    = Path("data/games_full.snap.json")

_CJK = re.compile(r"[\u4E00-\u9FFF\u3400-\u4DBF]")

def slugify(s: str) -> str:
    """更穩定的 slug：壓小寫、去頭尾空白、非英數轉成單一 -、移除前後 -。"""
    s = (s or "").strip().lower()
    out = []
    prev_dash = False
    for ch in s:
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        else:
            if not prev_dash:
                out.append("-")
                prev_dash = True
    res = "".join(out).strip("-")
    return res or "game"

def _int_or_none(x):
    if x is None: return None
    s = str(x).strip()
    if s == "" or s.lower() == "none": return None
    try:
        return int(float(s))
    except:
        return None

def _float_or_none(x):
    if x is None: return None
    s = str(x).strip()
    if s == "" or s.lower() == "none": return None
    try:
        return float(s)
    except:
        return None

def _has_zh(name_zh: str, name_en: str) -> bool:
    s = (name_zh or "") + " " + (name_en or "")
    return bool(_CJK.search(s))

def _overall_rank_of(r: dict):
    """盡量取出總排名；支援 r['ranks'] 為 dict 的不同鍵名。"""
    v = r.get("rank_overall")
    if v is None:
        v = r.get("rank")
    if isinstance(v, dict):
        v = v.get("boardgame") or v.get("overall") or v.get("all")
    return _int_or_none(v)

def make_id(r: dict) -> str:
    """
    穩定 ID 策略：
    - 有 bgg_id：以 "bgg{bid}" 為核心；若有 image_override ⇒ 加 md5；若有 image_version ⇒ 加 -v{ver}
      → 收藏鍵與差異友善（同一款不同賣家仍歸於同遊戲，符合前端收藏行為）。
    - 無 bgg_id：用名稱 slug 為核心，同樣附加 image_override md5 或版本號。
    """
    bid = _int_or_none(r.get("bgg_id"))
    img_ovr = r.get("image_override")
    ver = r.get("image_version_id") or r.get("image_version_used")

    if bid:
        base = f"bgg{bid}"
    else:
        base = slugify(r.get("name_en_override") or r.get("name_en") or r.get("name_zh") or "game")

    if img_ovr:
        sig = hashlib.md5(str(img_ovr).encode("utf-8")).hexdigest()[:8]
        return f"{base}-{sig}"
    if ver:
        return f"{base}-v{str(ver).strip()}"
    return base

def main():
    if not INPUT.exists():
        print("No data/bgg_data.json; skip build_json.")
        return

    rows  = json.loads(INPUT.read_text(encoding="utf-8"))
    items = []
    today = datetime.date.today().isoformat()

    for r in rows:
        # 名稱
        name_zh = r.get("name_zh")
        name_en = r.get("name_en_override") or r.get("name_en") or r.get("bgg_query") or ""

        # 影像（支援覆蓋）
        image = r.get("image") or r.get("image_url") or r.get("thumb_url") or ""
        if r.get("image_override"):
            image = r["image_override"]

        # 玩家數
        pmin = _int_or_none(r.get("min_players") or r.get("minplayers") or r.get("players_min"))
        pmax = _int_or_none(r.get("max_players") or r.get("maxplayers") or r.get("players_max"))
        players = [pmin, pmax] if (pmin or pmax) else None

        # 價格/庫存（保持數字或 None）
        price_msrp = _int_or_none(r.get("price_msrp_twd"))
        price_new  = _int_or_none(r.get("price_twd"))
        price_used = _int_or_none(r.get("used_price_twd"))
        stock      = _int_or_none(r.get("stock"))

        # 評分/難度/排名
        rating_avg   = _float_or_none(r.get("rating_avg")   or r.get("avg_rating")   or r.get("rating"))
        rating_bayes = _float_or_none(r.get("rating_bayes") or r.get("bayes_average") or r.get("bayes_avg"))
        weight       = _float_or_none(r.get("weight")       or r.get("complexity")   or r.get("avg_weight"))
        rank_overall = _overall_rank_of(r)

        # 基本欄位複製 + 正規化覆蓋
        item = dict(r)
        item["id"]       = make_id(r)
        item["name_zh"]  = name_zh or ""
        item["name_en"]  = name_en or ""
        item["image"]    = image or ""

        bid = _int_or_none(r.get("bgg_id"))
        if bid and not item.get("bgg_url"):
            item["bgg_url"] = f"https://boardgamegeek.com/boardgame/{bid}"

        #  players
        if players:
            # 若有缺一側，用已知值補另一側，避免 [n, None]
            a = players[0] if players[0] is not None else players[1]
            b = players[1] if players[1] is not None else players[0]
            item["players"] = [a, b]

        # prices / stock
        item["price_msrp_twd"] = price_msrp
        item["price_twd"]      = price_new
        item["used_price_twd"] = price_used
        item["stock"]          = stock

        # ratings / weight / rank
        item["rating_avg"]     = rating_avg
        item["rating_bayes"]   = rating_bayes
        item["weight"]         = weight
        item["rank_overall"]   = rank_overall

        # 關鍵字（若缺）
        if not item.get("search_keywords"):
            kws=[]
            if name_zh: kws.append(f"{name_zh} BGG")
            if name_en: kws.append(f"{name_en} BGG")
            item["search_keywords"] = kws

        # 中文名旗標
        item["has_zh_name"] = _has_zh(item.get("name_zh"), item.get("name_en"))

        # 更新日
        item["updated_at"] = today

        # 類別/機制 欄位標準化為陣列（若來源為 None/空字串）
        for k in ("categories", "categories_zh", "mechanics", "mechanics_zh", "aliases_zh", "search_keywords"):
            v = item.get(k)
            if v is None or v == "":
                item[k] = []
            elif not isinstance(v, list):
                item[k] = [v]

        items.append(item)

    # 保持穩定輸出：中文優先 → 名稱字母序（與前端排序策略相容，利於快取/PR diff）
    def _sort_key(x):
        n = (x.get("name_zh") or x.get("name_en") or "").lower()
        zh_key = 0 if _has_zh(x.get("name_zh"), x.get("name_en")) else 1
        return (zh_key, n)

    items.sort(key=_sort_key)

    # 輸出主檔
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(items, ensure_ascii=False, indent=2)
    OUTPUT.write_text(text, encoding="utf-8")

    # 同步輸出備援快照（供前端 fallback）
    SNAP.write_text(text, encoding="utf-8")

    print(f"Built {len(items)} entries → {OUTPUT}")
    print(f"Snapshot written → {SNAP}")

if __name__ == "__main__":
    main()

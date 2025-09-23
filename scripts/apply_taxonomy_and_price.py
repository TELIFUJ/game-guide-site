# scripts/apply_taxonomy_and_price.py
import csv, json
from pathlib import Path
from collections import defaultdict

MANUAL_CSV = Path("data/manual.csv")
BGG_IN     = Path("data/bgg_data.json")
BGG_OUT    = BGG_IN
CATMAP_CSV = Path("data/category_map_zh.csv")
MECHMAP_CSV= Path("data/mechanism_map_zh.csv")

MECH_SEED = {
  "Action Points":"行動點","Area Majority / Influence":"區域控制","Area Movement":"區域移動",
  "Auction / Bidding":"競標","Bag Building":"布袋構築","Campaign / Battle Card Driven":"戰役/卡驅動",
  "Card Drafting":"選牌","Card Play Conflict Resolution":"出牌解衝突","Cooperative Game":"合作",
  "Contracts":"合約","Deck Construction":"牌庫構築","Dice Rolling":"擲骰","End Game Bonuses":"終局加分",
  "Grid Movement":"格子移動","Hand Management":"手牌管理","Hidden Movement":"隱藏移動",
  "Line Drawing":"連線","Loans":"借貸","Memory":"記憶","Modular Board":"模組地圖",
  "Movement Points":"移動點","Network and Route Building":"路網建設","Negotiation":"談判",
  "Open Drafting":"公開選牌","Ownership":"所有權","Pattern Recognition":"圖形辨識",
  "Pick-up and Deliver":"取貨運送","Press Your Luck":"拚運氣","Rock-Paper-Scissors":"剪刀石頭布",
  "Role Playing":"角色扮演","Scenario / Mission / Campaign Game":"劇本/任務/戰役",
  "Set Collection":"收集套組","Simultaneous Action Selection":"同時選擇行動",
  "Solo / Solitaire Game":"單人","Square Grid":"方格","Take That":"互害",
  "Tile Placement":"板塊擺放","Trading":"交易","Trick-taking":"吃墩",
  "Turn Order: Claim Action":"搶先手","Variable Phase Order":"可變階段順序",
  "Variable Player Powers":"角色能力","Variable Set-up":"可變設置",
  "Worker Placement":"工人放置","Worker Placement with Dice Workers":"骰子工人"
}

def _int_or_none(x):
    if x is None: return None
    s = str(x).strip()
    if s == "" or s.lower() == "none": return None
    try: return int(float(s))
    except: return None

def load_manual_multi():
    """同一個 key（bgg_id/name_zh/bgg_query）允許多筆。"""
    by_key = defaultdict(list)
    if not MANUAL_CSV.exists(): return by_key
    with MANUAL_CSV.open(encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            row["manual_override"] = int(row.get("manual_override") or 0)
            row["price_msrp_twd"]  = _int_or_none(row.get("price_msrp_twd"))
            row["price_twd"]       = _int_or_none(row.get("price_twd"))
            row["used_price_twd"]  = _int_or_none(row.get("used_price_twd"))
            row["stock"]           = _int_or_none(row.get("stock"))
            if row.get("image_version_id") is not None:
                row["image_version_id"] = str(row["image_version_id"]).strip()

            for key in (str(row.get("bgg_id") or "").strip(),
                        str(row.get("name_zh") or "").strip(),
                        str(row.get("bgg_query") or "").strip()):
                if key:
                    by_key[key].append(row)
    return by_key

def load_map(csv_path, key_en, key_zh):
    m = {}
    if not csv_path.exists(): return m
    with csv_path.open(encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            en = (row.get(key_en) or "").strip()
            zh = (row.get(key_zh) or "").strip()
            if en: m[en] = zh or en
    return m

def apply_manual_fields(base, m):
    out = dict(base)
    for fld in [
        "name_zh","name_en_override","alias_zh","category_zh",
        "price_msrp_twd","price_twd","used_price_twd",
        "price_note","used_note","manual_override","stock",
        "description",
        # 圖片控制（兩個都支援）
        "image_override","image_version_id",
        # （可選）自訂連結
        "link_override","bgg_url_override",
    ]:
        if fld in m and m[fld] not in (None, ""):
            out[fld] = m[fld]

    # 別名 → 陣列
    if out.get("alias_zh"):
        out["aliases_zh"] = [x.strip() for x in str(out["alias_zh"]).split(";") if x.strip()]
    return out

def main():
    if not BGG_IN.exists():
        print("No data/bgg_data.json; skip apply."); return

    manual_multi = load_manual_multi()
    catmap = load_map(CATMAP_CSV, "bgg_category_en", "category_zh")
    mechmap = load_map(MECHMAP_CSV, "bgg_mechanism_en", "mechanism_zh")

    base_rows = json.loads(BGG_IN.read_text(encoding="utf-8"))
    out = []

    for r in base_rows:
        keys = [str(r.get("bgg_id") or "").strip(),
                str(r.get("name_zh") or "").strip(),
                str(r.get("bgg_query") or "").strip()]
        manuals = None
        for k in keys:
            if k and k in manual_multi:
                manuals = manual_multi[k]; break

        if not manuals:
            out.append(r)
        else:
            for m in manuals:
                out.append(apply_manual_fields(r, m))

    # 中文分類 & 機制中文
    for r in out:
        if r.get("category_zh"):
            r["categories_zh"] = [x.strip() for x in str(r["category_zh"]).replace("；",";")
                                  .replace("/", ";").split(";") if x.strip()]
        else:
            en = r.get("categories") or []
            r["categories_zh"] = [catmap.get(x, x) for x in en]

        mechs = r.get("mechanics") or []
        r["mechanics_zh"] = [mechmap.get(x) or MECH_SEED.get(x) or x for x in mechs]

    BGG_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"apply_taxonomy_and_price: total {len(out)}; categories_zh & mechanics_zh applied.")

if __name__ == "__main__":
    main()

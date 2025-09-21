# scripts/apply_taxonomy_and_price.py
import csv, json
from pathlib import Path

MANUAL_CSV=Path("data/manual.csv")
BGG_IN=Path("data/bgg_data.json")
BGG_OUT=BGG_IN
CATMAP_CSV=Path("data/category_map_zh.csv")
MECHMAP_CSV=Path("data/mechanism_map_zh.csv")

# 常見機制中文後援（可再加）
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
    s=str(x).strip()
    if s=="" or s.lower()=="none": return None
    try: return int(float(s))
    except: return None

def load_manual():
    d={}
    if not MANUAL_CSV.exists(): return d
    with MANUAL_CSV.open(encoding="utf-8-sig") as f:
        r=csv.DictReader(f)
        for row in r:
            key=str(row.get("bgg_id") or row.get("name_zh") or row.get("bgg_query"))
            if not key: continue
            row["manual_override"]=int(row.get("manual_override") or 0)
            row["price_msrp_twd"]=_int_or_none(row.get("price_msrp_twd"))
            row["price_twd"]=_int_or_none(row.get("price_twd"))
            row["used_price_twd"]=_int_or_none(row.get("used_price_twd"))
            row["stock"]=_int_or_none(row.get("stock"))
            if row.get("image_version_id") is not None:
                row["image_version_id"]=str(row["image_version_id"]).strip()
            d[key]=row
    return d

def load_map(csv_path, key_en, key_zh):
    m={}
    if not csv_path.exists(): return m
    with csv_path.open(encoding="utf-8-sig") as f:
        r=csv.DictReader(f)
        for row in r:
            en=(row.get(key_en) or "").strip()
            zh=(row.get(key_zh) or "").strip()
            if en: m[en]=zh
    return m

def main():
    if not BGG_IN.exists():
        print("No data/bgg_data.json; skip apply."); return
    manual=load_manual()
    catmap=load_map(CATMAP_CSV,"bgg_category_en","category_zh")
    mechmap=load_map(MECHMAP_CSV,"bgg_mechanism_en","mechanism_zh")

    rows=json.loads(BGG_IN.read_text(encoding="utf-8"))
    out=[]
    for r in rows:
        # 合併手動欄位
        m=None
        for k in [str(r.get("bgg_id") or ""), str(r.get("name_zh") or ""), str(r.get("bgg_query") or "")]:
            if k and k in manual: m=manual[k]; break
        if m:
            for fld in ["name_zh","name_en_override","alias_zh","category_zh","price_msrp_twd",
                        "price_twd","used_price_twd","price_note","used_note","manual_override",
                        "stock","description","image_override","image_version_id"]:
                if fld in m and m[fld] not in (None,""):
                    r[fld]=m[fld]

        # 中文分類
        if r.get("category_zh"):
            r["categories_zh"]=[x.strip() for x in str(r["category_zh"]).replace("；",";").replace("/", ";").split(";") if x.strip()]
        else:
            en=r.get("categories") or []
            r["categories_zh"]=[(catmap.get(x) or x) for x in en]

        # 機制中文（map → seed → 英文）
        mechs=r.get("mechanics") or []
        zh=[]
        for en in mechs:
            zh.append(mechmap.get(en) or MECH_SEED.get(en) or en)
        r["mechanics_zh"]=zh

        # 別名
        if r.get("alias_zh"):
            r["aliases_zh"]=[x.strip() for x in str(r["alias_zh"]).split(";") if x.strip()]

        out.append(r)

    BGG_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"apply_taxonomy_and_price: total {len(out)}; categories_zh & mechanics_zh applied.")
if __name__ == "__main__": main()

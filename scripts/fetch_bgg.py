# --- fetch_bgg.py（覆蓋 main） ---
def main():
    if not INPUT.exists():
        print("No data/bgg_ids.json; nothing to fetch."); return

    base_rows = json.loads(INPUT.read_text(encoding="utf-8"))

    # 1) 建立：一個 bgg_id 對應「多筆」 base rows
    from collections import defaultdict
    rows_by_id = defaultdict(list)
    ids_unique = []
    for r in base_rows:
        bid = r.get("bgg_id")
        if not bid:
            continue
        bid = int(bid)
        rows_by_id[bid].append(r)
        if bid not in ids_unique:
            ids_unique.append(bid)

    results = []
    for i in range(0, len(ids_unique), BATCH):
        chunk = ids_unique[i:i+BATCH]
        try:
            root   = fetch_batch(chunk)
            parsed = parse_items(root)   # 每個 id 回來一筆 p
            # 2) 一個 p（同 id）要複製成 N 份，分別合併同 id 的 base row
            for p in parsed:
                bid = int(p["bgg_id"])
                bases = rows_by_id.get(bid, [{}])
                for base in bases:
                    # p 為 BGG 抽到的資料，base 為該列自家的欄位
                    # 讓 apply_taxonomy_and_price 之後再覆蓋手動欄位（price/name_zh/...）
                    results.append({**base, **p})
        except Exception as e:
            print(f"Batch {chunk} failed: {e}")
        time.sleep(3)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fetched {len(results)} entries → {OUTPUT}")

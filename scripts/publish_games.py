#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC1 = ROOT / "data" / "games_full.json"
SRC2 = ROOT / "data" / "bgg_data.json"
OUT = ROOT / "site" / "data" / "games.json"

SRC = SRC1 if SRC1.exists() else SRC2
if not SRC.exists():
    raise SystemExit(f"[publish_games] 找不到來源：{SRC1} / {SRC2}")

data = json.loads(SRC.read_text(encoding="utf-8"))
if isinstance(data, dict):
    data = list(data.values())

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
print(f"publish_games: wrote {len(data)} → {OUT}")

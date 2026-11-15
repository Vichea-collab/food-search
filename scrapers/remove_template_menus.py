"""
Facts-only cleanup of data/restaurants.csv: remove the menus and prices that were never read from a real source.

Why: scrapers/enrich_all_menus.py and scrapers/enrich_street_food_menus.py gave "typical" menus (and a benchmark price)
to places that have none, by pattern: 664 unrelated cafes got the same Num Pang menu, bars the same skewers, a sushi
bar a Khmer soup menu. Those menus fed the dish matching, the "cheap" filter and the evaluation labels, but nothing
says the place sells them. A menu is kept only when it comes from:

  foodpanda  the place's own Foodpanda page (data/scraped/foodpanda_details.jsonl, read by
             scrapers/foodpanda_detail_scraper.py), id "fp-..."
  chain      a chain's own menu (data/scraped/brand_menus.json) on a branch that is that chain
  (others)   any menu not from these two is removed

What it does:
  * adds the column `menu_source` ("foodpanda", "chain:<brand>" or "" for no menu),
  * clears `menu` and `price_usd` on every other row (price_usd only ever came from those menus),
  * saves what it removed in data/raw/removed_template_menus.csv, so nothing is lost,
  * leaves every other column alone.

  python scrapers/remove_template_menus.py                 # dry run: prints the numbers, writes nothing
  python scrapers/remove_template_menus.py --out FILE      # writes the cleaned file to FILE
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "data/restaurants.csv"
DETAILS = ROOT / "data/scraped/foodpanda_details.jsonl"
BRANDS = ROOT / "data/scraped/brand_menus.json"
REMOVED = ROOT / "data/raw/removed_template_menus.csv"

# Rows that carry a chain's menu but are another business (checked by hand, 13 Nov 2026).
NOT_THAT_CHAIN = {
    "overture-81a3c254-409",     # The Pizza Box           (not The Pizza Company)
    "overture-6c838c1b-9ca",     # Koi Garden Coffee       (not KOI Thé)
    "overture-fc5f88d3-9a4",     # ខយ ហ្គាឌិន - Koi Garden  (not KOI Thé)
    "fp-uhwx",                   # Koi Maachaa Bkk         (not KOI Thé)
    "overture-5c847002-9e2",     # Amazon's Coffee         (not Café Amazon)
}


def item_names(menu) -> tuple:
    try:
        return tuple(sorted(str(i.get("name") or i.get("name_en") or "") for i in json.loads(menu)))
    except (ValueError, TypeError, AttributeError):
        return ()


def classify(d: pd.DataFrame) -> pd.Series:
    """menu_source for every row: 'foodpanda', 'chain:<brand>', 'template' (to remove) or '' (no menu)."""
    fp_ids = {json.loads(line)["id"] for line in DETAILS.open() if line.strip()}
    brands = json.load(BRANDS.open())
    chain = {tuple(sorted(str(i.get("name", "")) for i in v["menu"])): k for k, v in brands.items()}
    out = []
    for rid, menu in zip(d["id"], d["menu"]):
        if not menu.strip():
            out.append("")
        elif rid in fp_ids and rid.startswith("fp-"):
            out.append("foodpanda")
        elif item_names(menu) in chain and rid not in NOT_THAT_CHAIN:
            out.append("chain:" + chain[item_names(menu)])
        else:
            out.append("template")
    return pd.Series(out, index=d.index)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(MAIN))
    ap.add_argument("--out", help="write the cleaned file here (without it: dry run)")
    a = ap.parse_args()
    # read every cell as text: untouched columns come back exactly as they were (no 6.0 -> 6, no lost ids)
    d = pd.read_csv(a.src, dtype=str, keep_default_na=False)
    if "menu_source" in d.columns:
        d = d.drop(columns="menu_source")
    src = classify(d)
    bad = src.eq("template")
    print(f"{len(d)} places | menu kept: foodpanda {src.eq('foodpanda').sum()}, "
          f"chain {src.str.startswith('chain:').sum()} | removed: {bad.sum()} | had no menu: {src.eq('').sum()}")
    print("price_usd cleared on", int((bad & d['price_usd'].ne('')).sum()), "rows;",
          "price_usd left:", int((~bad & d['price_usd'].ne('')).sum()))
    if not a.out:
        return
    if bad.any():                      # never overwrite the record of an earlier cleanup with an empty one
        removed = d.loc[bad, ["id", "name", "source", "menu", "price_usd"]]
        REMOVED.parent.mkdir(parents=True, exist_ok=True)
        if REMOVED.exists():
            removed = pd.concat([pd.read_csv(REMOVED, dtype=str, keep_default_na=False), removed]).drop_duplicates("id")
        removed.to_csv(REMOVED, index=False)
    d.loc[bad, ["menu", "price_usd"]] = ""
    d["menu_source"] = src.where(~bad, "")
    cols = list(d.columns)                       # menu_source right after menu
    cols.insert(cols.index("menu") + 1, cols.pop(cols.index("menu_source")))
    d[cols].to_csv(a.out, index=False)
    print(f"wrote {a.out}" + (f"; removed menus saved in {REMOVED}" if bad.any() else ""))


if __name__ == "__main__":
    sys.exit(main())

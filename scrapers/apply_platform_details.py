"""
Adds what the delivery platforms really say about each place to the main dataset (data/restaurants.csv):

1. Foodpanda rows (id "fp-...") get their scraped details (scrapers/foodpanda_detail_scraper.py): rating, opening hours,
   phone, coordinates (when missing), cuisines and the full menu (name, description, price) in the `menu` column.
2. A new `delivery` column: JSON list [{"platform": "Foodpanda", "url": ...}, {"platform": "Grab", "url": ...}] of the
   delivery platforms the place is listed on, or "" when we found none. "" means "not found in our data", not "no".
   Matching, so a Grab / Foodpanda listing is only attached to a place that is really the same one:
   - Foodpanda: the place's own row, or a place with the same name within 150 m of the Foodpanda coordinates.
   - Grab (its sitemap has no coordinates): the same name in the same city.

  python scrapers/apply_platform_details.py            # writes data/scraped/restaurants_enriched.csv (nothing else changes)
  python scrapers/apply_platform_details.py --apply    # also replaces data/restaurants.csv (the old file is kept as .bak)
"""
import argparse
import json
import math
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from food_search.search import canonical_place  # noqa: E402  (area/city spelling shared with the app)

MAIN = ROOT / "data/restaurants.csv"
DETAILS = ROOT / "data/scraped/foodpanda_details.jsonl"
GRAB = ROOT / "data/scraped/grabfood_places.csv"
OUT = ROOT / "data/scraped/restaurants_enriched.csv"
MAX_DISTANCE_M = 150
GENERIC_DISH = "Khmer & Asian Made-to-Order Dishes"


def name_keys(name) -> set:
    """Spellings of a name to compare: whole, Latin part and Khmer part, letters and digits only."""
    name = str(name or "").lower()
    outside = re.sub(r"\(.*?\)", " ", name)                      # "Pka Rik Thmey (ផ្ការីកថ្មី)" -> "pka rik thmey"
    parts = [name, outside, " ".join(re.findall(r"[a-z0-9 ]+", name)), " ".join(re.findall(r"[ក-៿ ]+", name))]
    keys = {re.sub(r"[^a-z0-9ក-៿]+", "", p) for p in parts}
    return {k for k in keys if len(k) >= 4}


def metres(lat1, lng1, lat2, lng2) -> float:
    return math.hypot((lat2 - lat1) * 111_320, (lng2 - lng1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2)))


def to_hour(text):
    m = re.match(r"^(\d{1,2}):(\d{2})", text or "")
    return round(int(m.group(1)) + int(m.group(2)) / 60, 2) if m else None


def apply_foodpanda(row: dict, det: dict) -> None:
    """Fill one dataset row from its Foodpanda page. Only real values; an empty field stays as it was."""
    if det.get("rating"):
        row["rating"] = str(det["rating"])
    if det.get("phone"):
        row["phone_public"] = det["phone"]
    if not row.get("lat") and det.get("lat") is not None:
        row["lat"], row["lng"] = str(det["lat"]), str(det["lng"])
    hours = det.get("hours") or []
    if hours:
        o, c = to_hour(hours[0].get("opens")), to_hour(hours[0].get("closes"))
        if o is not None and c is not None:
            row["open_hour"], row["close_hour"] = str(o), str(c)
    cuisines = [c for c in det.get("cuisines") or [] if c]
    if cuisines and (not row.get("dish_en") or row["dish_en"] == GENERIC_DISH or row.get("source") == "foodpanda"):
        row["dish_en"] = ", ".join(cuisines)
    menu = [{"name_en": it["name"], "description": it.get("description", ""), "price_usd": it.get("price_usd"),
             "category": it.get("category", "")} for it in det.get("menu") or [] if not it.get("sold_out")]
    if menu:
        row["menu"] = json.dumps(menu, ensure_ascii=False)
    bits = [f"Foodpanda restaurant in {det.get('city') or row.get('area', '')}, Cambodia."]
    if cuisines:
        bits.append(f"Cuisine: {', '.join(cuisines)}.")
    if det.get("address"):
        bits.append(f"Address: {det['address']}.")
    if det.get("reviews"):
        bits.append(f"{det['reviews']} reviews on Foodpanda.")
    row["description"] = " ".join(bits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="also replace data/restaurants.csv (backup kept as .bak)")
    args = ap.parse_args()

    df = pd.read_csv(MAIN, dtype=str, keep_default_na=False)
    if "delivery" not in df.columns:
        df["delivery"] = ""
    rows = df.to_dict("records")

    details = {}
    if DETAILS.exists():
        for line in DETAILS.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not d.get("gone"):
                details[d["id"]] = d
    print(f"{len(details)} Foodpanda pages with details")

    platforms = defaultdict(list)          # row index -> [{"platform", "url"}]

    # 1. Foodpanda: its own rows, then same-name places next to a Foodpanda coordinate
    by_name = defaultdict(list)
    for i, r in enumerate(rows):
        for k in name_keys(r["name"]):
            by_name[k].append(i)
    filled = 0
    for fid, det in details.items():
        own = next((i for i, r in enumerate(rows) if r["id"] == fid), None) if fid.startswith("fp-") else None
        if own is not None:
            apply_foodpanda(rows[own], det)
            filled += 1
            platforms[own].append({"platform": "Foodpanda", "url": det["url"]})
        if det.get("lat") is None:
            continue
        for k in name_keys(det.get("name")):
            for i in by_name.get(k, []):
                r = rows[i]
                if i == own or not r["lat"]:
                    continue
                if metres(float(r["lat"]), float(r["lng"]), det["lat"], det["lng"]) <= MAX_DISTANCE_M \
                        and not any(p["platform"] == "Foodpanda" for p in platforms[i]):
                    platforms[i].append({"platform": "Foodpanda", "url": det["url"]})
    print(f"{filled} Foodpanda rows filled with real details")

    # 2. Grab: same name in the same city
    if GRAB.exists():
        grab = pd.read_csv(GRAB, dtype=str, keep_default_na=False)
        index = defaultdict(list)
        for g in grab.itertuples():
            city = canonical_place(g.area)[1]
            for k in name_keys(g.name):
                index[(k, city)].append(g.source_url)
        for i, r in enumerate(rows):
            city = canonical_place(r.get("city") or r["area"])[1] or canonical_place(r["area"])[1]
            urls = [u for k in name_keys(r["name"]) for u in index.get((k, city), [])]
            if urls and not any(p["platform"] == "Grab" for p in platforms[i]):
                platforms[i].append({"platform": "Grab", "url": urls[0]})

    for i, r in enumerate(rows):
        r["delivery"] = json.dumps(platforms[i], ensure_ascii=False) if platforms.get(i) else ""
    out = pd.DataFrame(rows, columns=list(df.columns))
    out.to_csv(OUT, index=False)
    n = (out["delivery"] != "").sum()
    print(f"{n} of {len(out)} places have a delivery platform; with menu: {(out['menu'] != '').sum()}; saved to {OUT}")
    print("platform counts:", pd.Series([p["platform"] for v in platforms.values() for p in v]).value_counts().to_dict())
    if args.apply:
        shutil.copy(MAIN, MAIN.with_suffix(".csv.bak"))
        out.to_csv(MAIN, index=False)
        print(f"data/restaurants.csv replaced (old file: {MAIN.with_suffix('.csv.bak')})")


if __name__ == "__main__":
    main()

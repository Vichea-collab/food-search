"""
Take places that are not in Phnom Penh out of data/restaurants.csv. Foodpanda's sitemap lists every city and the
sitemap scraper labelled each place "Phnom Penh" unless a khan was in the slug, so Sihanoukville, Poipet and Kampong Speu
restaurants sat in the Phnom Penh dataset (measured 13 Nov 2026: 89 of 565 places whose Foodpanda page gives the city,
16%, were outside Phnom Penh).

A place is moved out when
  1. its Foodpanda page (data/scraped/foodpanda_details.jsonl) gives a city other than Phnom Penh, or
  2. its name ENDS with another city ("... Poi Pet", "... Chbar Mon"). Foodpanda puts the location last; a city in the
     middle is a dish style ("Kuy Teav Poipet St 253" is a noodle style sold in Phnom Penh). Checked on the 565 known
     places: 17 hits, 0 wrong. It finds only about a fifth of the others, so some are still left in the dataset.
Moved places go to data/raw/non_phnom_penh_places.csv (with the reason), so nothing is lost.

  venv/bin/python scrapers/remove_non_phnom_penh.py                  # dry run
  venv/bin/python scrapers/remove_non_phnom_penh.py --apply          # rewrite data/restaurants.csv
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
OUT = ROOT / "data/raw/non_phnom_penh_places.csv"
CITY = (r"(poi ?pet|siem ?reap|bavet|sihanouk(?:ville)?|kampot|battambang|kampong ?cham|kampong ?speu|takeo|kep|"
        r"ta ?kh?mao?u?|ta ?khmau|chbar ?mon|odongk|svay ?rieng|kratie|pursat|koh ?kong)")


def end_city(name: str):
    m = re.search(CITY + r"\s*(?:\d+)?\s*$", str(name).lower().strip())
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    d = pd.read_csv(MAIN, dtype=str, keep_default_na=False)
    city = {}
    for line in DETAILS.open():
        if line.strip():
            x = json.loads(line)
            city[x["id"]] = x.get("city") or ""
    real = d["id"].map(city)
    by_page = real.notna() & real.ne("") & real.ne("Phnom Penh")
    by_name = real.isna() & d["id"].str.startswith("fp-") & d["name"].map(end_city).notna()
    out = by_page | by_name
    reason = pd.Series("", index=d.index)
    reason[by_page] = "Foodpanda page says city: " + real[by_page]
    reason[by_name] = "name ends with: " + d.loc[by_name, "name"].map(end_city)
    print(f"{len(d)} places | moved out: {int(out.sum())} (Foodpanda page {int(by_page.sum())}, name {int(by_name.sum())})")
    print(reason[out].str.replace(r"^(.*?): ", "", regex=True).value_counts().head(10).to_dict())
    if not a.apply:
        return
    moved = d[out].assign(reason=reason[out])
    if OUT.exists():
        moved = pd.concat([pd.read_csv(OUT, dtype=str, keep_default_na=False), moved]).drop_duplicates("id")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    moved.to_csv(OUT, index=False)
    d[~out].to_csv(MAIN, index=False)
    print(f"wrote {MAIN} ({int((~out).sum())} places) and {OUT} ({len(moved)} places)")


if __name__ == "__main__":
    sys.exit(main())

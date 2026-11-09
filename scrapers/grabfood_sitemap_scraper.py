"""
GrabFood Cambodia merchant scraper (official sitemaps only).
Source: Grab's public sitemap index listed in https://food.grab.com/robots.txt
  https://growth-public.grab.com/grabfood-com/sitemap/sitemap_index.xml
Every Cambodian city has a merchant-info sitemap with one URL per restaurant: /kh/en/restaurant/<slug>/<id>.
Facts only: the sitemap gives the name, the city and the page link. Menu, price, rating, hours and coordinates are
loaded by Grab's app (not in the page), so they are left empty, never guessed. Only the sitemap files are fetched
(about 20, with a pause between them); the restaurant pages themselves are not crawled.
"""
import csv
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INDEX_URL = "https://growth-public.grab.com/grabfood-com/sitemap/sitemap_index.xml"
HEADERS = {"User-Agent": "Mozilla/5.0 (food-search course project; contact via GitHub)"}
PAUSE_S = 2          # Grab's robots.txt asks for Crawl-delay: 2
TODAY = time.strftime("%Y-%m-%d")

# slug -> proper city name where simple title-casing is wrong
CITY_NAMES = {"serei-saophoan": "Sisophon", "poipet": "Poipet", "bavet": "Bavet"}


def city_name(slug: str) -> str:
    return CITY_NAMES.get(slug, slug.replace("-", " ").title())


def clean_name(slug: str) -> str:
    """'chicken-cheese-ឈីកខិនឈីស--delivery' -> 'Chicken Cheese ឈីកខិនឈីស'"""
    s = unquote(slug)
    s = re.sub(r"-*-delivery$", "", s, flags=re.I)
    words = [w for w in s.split("-") if w]
    return " ".join(w.capitalize() if w.isascii() else w for w in words).strip()


def guess_dish(name: str):
    """Dish type only when the name says it (reuses the Foodpanda keyword table); otherwise left empty."""
    from scrapers.foodpanda_sitemap_scraper import CUISINE_MAPPINGS
    text = name.replace(" ", "-")
    for pattern, dish_en, dish_kh, _price in CUISINE_MAPPINGS:
        if pattern.search(text):
            return dish_en, dish_kh
    return "", ""


def kh_city_sitemaps() -> list:
    r = requests.get(INDEX_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    urls = re.findall(r"<loc>([^<]+)</loc>", r.text)
    return sorted(u for u in urls if re.search(r"/sitemap/kh/[a-z-]+/en/merchant-info-\d+\.xml$", u))


def scrape_grabfood_merchants() -> list:
    places, seen = [], set()
    sitemaps = kh_city_sitemaps()
    print(f"{len(sitemaps)} Cambodian city sitemaps on Grab")
    for n, sm in enumerate(sitemaps):
        city_slug = re.search(r"/kh/([a-z-]+)/en/", sm).group(1)
        area = city_name(city_slug)
        if n:
            time.sleep(PAUSE_S)
        try:
            r = requests.get(sm, headers=HEADERS, timeout=60)
            r.raise_for_status()
        except requests.RequestException as exc:
            print(f"  skip {sm}: {exc}")
            continue
        added = 0
        for u in BeautifulSoup(r.content, "xml").find_all("url"):
            loc = (u.find("loc").text or "").strip()
            m = re.search(r"/restaurant/([^/]+)/([^/?#]+)$", loc)
            if not m or m.group(2) in seen:
                continue
            seen.add(m.group(2))
            name = clean_name(m.group(1))
            if not name:
                continue
            kh_url = next((l.get("href") for l in u.find_all("xhtml:link") if l.get("hreflang", "").startswith("km")), "")
            dish_en, dish_kh = guess_dish(name)
            places.append({
                "id": f"grab-{m.group(2)}", "name": name, "dish_en": dish_en, "dish_kh": dish_kh,
                "description": f"GrabFood restaurant in {area}, Cambodia. Order via the Grab app: {loc}",
                "tags": "grabfood;delivery;restaurant", "price_usd": "", "area": area, "lat": "", "lng": "",
                "rating": "", "open_hour": "", "close_hour": "", "source": "grabfood-sitemap", "source_url": loc,
                "date": TODAY, "image_path": "", "phone_public": "", "page_url": kh_url,
            })
            added += 1
        print(f"  {area}: {added}")
    return places


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="GrabFood Cambodia merchants from Grab's official sitemaps")
    ap.add_argument("--output", default="data/scraped/grabfood_places.csv")
    args = ap.parse_args()
    rows = scrape_grabfood_merchants()
    print(f"Scraped {len(rows)} GrabFood merchants across Cambodia")
    if rows:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"Saved to {out}")
        print(Counter(r["area"] for r in rows).most_common())

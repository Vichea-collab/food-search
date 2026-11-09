"""
Foodpanda Cambodia detail scraper: the real menu, rating, hours, phone and coordinates of each restaurant.
Reads data/scraped/foodpanda_places.csv (the sitemap scraper's list), opens each public restaurant page once
(robots.txt allows /restaurant/ pages) and reads what the page itself contains:
  - schema.org JSON-LD: address, coordinates, opening hours, cuisines, price range, delivery methods
  - the page's own data blob: rating, review count, phone, and every menu item (category, name, description, price)
Nothing is guessed: a field the page does not give stays empty. Output: one JSON object per line in
data/scraped/foodpanda_details.jsonl. The run is resumable (done pages are skipped) and polite (a pause between pages).

  python scrapers/foodpanda_detail_scraper.py --limit 20        # try a few
  python scrapers/foodpanda_detail_scraper.py                   # all, resumes where it stopped
  python scrapers/foodpanda_detail_scraper.py --city "Phnom Penh"   # only places in that city (districts included)
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
SRC = ROOT / "data/scraped/foodpanda_places.csv"
OUT = ROOT / "data/scraped/foodpanda_details.jsonl"
HEADERS = {"User-Agent": "Mozilla/5.0 (food-search course project)", "Accept-Language": "en"}
PAUSE_S = 8              # Foodpanda answers 403 when pages are fetched fast: one page every 8 s
BACKOFF_S = 300          # after a 403 wait 5 minutes; MAX_BLOCKS in a row = Foodpanda says stop: the run ends
MAX_BLOCKS = 3


def _json_ld(html: str) -> dict:
    m = re.search(r'data-testid="restaurant-seo-schema"[^>]*>(.*?)</script>', html, re.S)
    try:
        return json.loads(m.group(1)) if m else {}
    except ValueError:
        return {}


def _apollo(html: str) -> dict:
    """The page's Apollo cache (menu products and categories), or {}."""
    m = re.search(r"window\.__PROVIDER_PROPS__\s*=\s*(\{.*?\})\s*</script>", html, re.S)
    if not m:
        return {}
    try:
        props = json.loads(re.sub(r":undefined", ":null", m.group(1)))
    except ValueError:
        return {}
    return ((props.get("apollo") or {}).get("initialState")) or {}


def parse_page(html: str) -> dict:
    ld, cache = _json_ld(html), _apollo(html)
    info = {}
    m = re.search(r'"customer_phone":"([^"]*)","budget":(\d+),"rating":([\d.]+),"review_number":(\d+)', html)
    if m:
        info = {"phone": m.group(1), "budget": int(m.group(2)), "rating": float(m.group(3)), "reviews": int(m.group(4))}
    hours = []
    for spec in ld.get("openingHoursSpecification") or []:
        days = spec.get("dayOfWeek") or []
        hours.append({"days": days if isinstance(days, list) else [days], "opens": spec.get("opens"), "closes": spec.get("closes")})
    items = []
    for key, p in cache.items():
        if not key.startswith("RestaurantProductData:") or not p.get("title"):
            continue
        cat = cache.get(((p.get("menuCategory") or {}).get("__ref")) or "", {})
        price = (p.get("priceAttributes") or {}).get("originalPrice")
        items.append({"category": cat.get("name") or cat.get("title") or "", "name": p["title"],
                      "description": p.get("description") or "", "price_usd": price,
                      "sold_out": bool(p.get("isSoldOut"))})
    geo, addr = ld.get("geo") or {}, ld.get("address") or {}
    return {
        "name": ld.get("name"), "address": addr.get("streetAddress"), "city": addr.get("addressLocality"),
        "lat": geo.get("latitude"), "lng": geo.get("longitude"),
        "cuisines": ld.get("servesCuisine") or [], "price_range": ld.get("priceRange"),
        "delivery_methods": [d.rsplit("DeliveryMode", 1)[-1] for d in ld.get("deliveryMethod") or []],
        "hours": hours, "rating": info.get("rating") or None, "reviews": info.get("reviews") or 0,
        "phone": info.get("phone") or None, "menu": items,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="stop after this many new pages (0 = all)")
    ap.add_argument("--city", default="", help='only this city, e.g. "Phnom Penh" (its districts count as the city)')
    args = ap.parse_args()
    places = pd.read_csv(SRC, dtype=str, keep_default_na=False)
    if args.city:
        from food_search.search import canonical_place        # same area -> city spelling as the app
        places = places[places.area.map(lambda a: canonical_place(a)[1]) == args.city]
    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["id"])
            except (ValueError, KeyError):
                pass
    # "-pandasend" listings are Foodpanda's parcel courier service, not places to eat: skipped
    todo = [r for r in places.itertuples() if r.id not in done and "pandasend" not in r.source_url.lower()]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(done)} done, {len(todo)} to fetch")
    sess = requests.Session()
    sess.headers.update(HEADERS)
    blocks = 0
    with open(OUT, "a", encoding="utf-8") as out:
        for n, r in enumerate(todo, 1):
            try:
                resp = sess.get(r.source_url, timeout=(10, 30))
                resp.encoding = "utf-8"
                if resp.status_code == 404:
                    rec = {"id": r.id, "url": r.source_url, "gone": True}
                else:
                    resp.raise_for_status()
                    rec = {"id": r.id, "url": r.source_url, **parse_page(resp.text)}
            except requests.RequestException as exc:
                print(f"  {r.id}: {exc}")
                if getattr(exc.response, "status_code", 0) == 403:
                    blocks += 1
                    if blocks >= MAX_BLOCKS:
                        print(f"Foodpanda refused {MAX_BLOCKS} times in a row (403). Stopping; run again later to resume.")
                        return
                    print(f"  403: waiting {BACKOFF_S // 60} minutes")
                    time.sleep(BACKOFF_S)
                else:
                    time.sleep(5)
                continue
            blocks = 0
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            if n % 50 == 0 or n <= 3:
                print(f"  {n}/{len(todo)} {rec.get('name')} - {len(rec.get('menu', []))} items, rating {rec.get('rating')}")
            time.sleep(PAUSE_S)


if __name__ == "__main__":
    sys.exit(main())

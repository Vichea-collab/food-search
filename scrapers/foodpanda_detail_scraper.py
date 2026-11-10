"""
Foodpanda Cambodia detail scraper: the real menu, rating, hours, phone and coordinates of each restaurant.
Reads data/scraped/foodpanda_places.csv (the sitemap scraper's list), opens each public restaurant page once
(robots.txt is checked before each page: scrapers/robots.py) and reads what the page itself contains:
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
import random
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests
try:                               # scrapers/robots.py: obey robots.txt and the site's crawl delay
    from scrapers import robots
except ImportError:
    import robots

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
SRC = ROOT / "data/scraped/foodpanda_places.csv"
OUT = ROOT / "data/scraped/foodpanda_details.jsonl"
HEADERS = {"User-Agent": "Mozilla/5.0 (food-search course project)", "Accept-Language": "en"}
PAUSE_S = 8              # Foodpanda answers 403 when pages are fetched fast: one page every 8 s to start with
MAX_PAUSE_S = 45         # each 403 makes the pause 1.5x longer, up to this
BACKOFF_S = 300          # after a 403 wait 5 minutes; each further 403 makes that wait 2x longer, up to MAX_BACKOFF_S
MAX_BACKOFF_S = 1800     # (Foodpanda limits pages per hour: a short wait lets one page through and blocks again)
CALM_PAGES = 25          # this many pages in a row without a 403: the waits go back down one step
MAX_BLOCKS = 4           # MAX_BLOCKS 403s in a row = Foodpanda says stop: the run ends


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
    ap.add_argument("--pause", type=float, default=PAUSE_S, help="seconds between pages to start with (grows after a 403)")
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
    blocks, pause, n = 0, args.pause, 0
    backoff, calm = BACKOFF_S, 0
    with open(OUT, "a", encoding="utf-8") as out:
        while n < len(todo):
            r = todo[n]
            try:
                resp = robots.get(r.source_url, session=sess, timeout=(10, 30))
                resp.encoding = "utf-8"
                if resp.status_code == 404:
                    rec = {"id": r.id, "url": r.source_url, "gone": True}
                else:
                    resp.raise_for_status()
                    rec = {"id": r.id, "url": r.source_url, **parse_page(resp.text)}
            except requests.RequestException as exc:
                print(f"  {r.id}: {exc}")
                if isinstance(exc, robots.Disallowed) and robots.rules(r.source_url).disallow_all:
                    # robots.txt could not be read (5xx / no answer), not a page it forbids: wait and retry this
                    # page, instead of skipping every page until robots.txt is asked again
                    print(f"  robots.txt unreadable: waiting {robots.RETRY_S // 60} minutes; retrying this page", flush=True)
                    time.sleep(robots.RETRY_S)
                elif getattr(exc.response, "status_code", 0) == 403:
                    blocks += 1
                    if blocks >= MAX_BLOCKS:
                        print(f"Foodpanda refused {MAX_BLOCKS} times in a row (403). Stopping; run again later to resume.")
                        return
                    pause = min(pause * 1.5, MAX_PAUSE_S)
                    print(f"  403 ({time.strftime('%H:%M')}, {n} new pages so far): waiting {backoff // 60} minutes, "
                          f"then one page every ~{pause:.0f} s; retrying this page", flush=True)
                    time.sleep(backoff)
                    backoff, calm = min(backoff * 2, MAX_BACKOFF_S), 0
                else:
                    n += 1                                   # another error: skip the page (the next run retries it)
                    time.sleep(5)
                continue
            n += 1
            blocks, calm = 0, calm + 1
            if calm >= CALM_PAGES and backoff > BACKOFF_S:
                backoff, pause, calm = max(BACKOFF_S, backoff // 2), max(args.pause, pause / 1.5), 0
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            if n % 50 == 0 or n <= 3:
                print(f"  {n}/{len(todo)} {rec.get('name')} - {len(rec.get('menu', []))} items, rating {rec.get('rating')}")
            time.sleep(pause * random.uniform(0.7, 1.3))   # not a fixed beat: evenly spaced requests look like a bot


if __name__ == "__main__":
    sys.exit(main())

"""
GrabFood Cambodia Scraper & Category Harvester
Source: https://food.grab.com/kh/en/
Extracts: Phnom Penh category shortcuts, cuisine taxonomies, and merchant metadata.
"""

import re
import csv
import json
import logging
from pathlib import Path
from bs4 import BeautifulSoup
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://food.grab.com"
HOME_EN = f"{BASE_URL}/kh/en/"
HOME_KH = f"{BASE_URL}/kh/km/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CATEGORY_MAP_KH = {
    "khmer": "ម្ហូបខ្មែរ",
    "khmer-noodle": "គុយទាវ/មី",
    "asian": "ម្ហូបអាស៊ី",
    "coffee": "កាហ្វេ",
    "bubble-tea": "តែគុជ",
    "fast-food": "អាហាររហ័ស",
    "fried-rice": "បាយឆា",
    "burger": "ប៊ឺហ្គឺ",
    "pizza": "ភីហ្សា",
    "sushi": "ស៊ូស៊ី",
    "bread": "នំប៉័ង",
    "breakfast": "អាហារពេលព្រឹក",
    "lunch": "អាហារថ្ងៃត្រង់",
    "pastry": "នំខេក",
    "snack": "អាហារសម្រន់",
}

def scrape_grabfood_categories() -> list[dict]:
    print(f"Fetching GrabFood Cambodia home: {HOME_EN}")
    r = requests.get(HOME_EN, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    
    # Extract Next.js data
    next_data_el = soup.find("script", id="__NEXT_DATA__")
    categories = []
    seen = set()

    if next_data_el:
        try:
            data = json.loads(next_data_el.string)
            props = data.get("props", {}).get("pageProps", {})
            location = props.get("routeState", {}).get("location", {})
            lat = location.get("latitude", 11.5564)
            lng = location.get("longitude", 104.9282)
            print(f"GrabFood default location: Phnom Penh ({lat}, {lng})")
        except Exception as e:
            logger.warning(f"Error parsing __NEXT_DATA__: {e}")

    # Extract all category links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.search(r"category=([a-z0-9\-]+)-(\d+)", href)
        if m:
            cat_slug = m.group(1)
            cat_id = m.group(2)
            cat_name = cat_slug.replace("-", " ").title()
            cat_kh = CATEGORY_MAP_KH.get(cat_slug, "")
            
            if cat_id in seen:
                continue
            seen.add(cat_id)

            full_url = f"{BASE_URL}{href}" if href.startswith("/") else href
            categories.append({
                "id": f"grab-cat-{cat_id}",
                "name": f"GrabFood {cat_name} Phnom Penh",
                "dish_en": cat_name.lower(),
                "dish_kh": cat_kh,
                "description": f"GrabFood Cambodia category directory for {cat_name} in Phnom Penh central dining hubs.",
                "tags": f"grabfood;delivery;{cat_slug.replace('-', ';')}",
                "price_usd": "",
                "area": "Phnom Penh",
                "lat": "",  # facts only: not given by the source, so left empty (never a default) (a category page, not a place)
                "lng": "",
                "rating": "",
                "open_hour": "",
                "close_hour": "",
                "source": "grabfood",
                "source_url": full_url,
                "date": "2026-11-04",
                "image_path": "",
                "phone_public": "",
                "page_url": full_url.replace("/kh/en/", "/kh/km/"),
            })

    return categories

if __name__ == "__main__":
    cats = scrape_grabfood_categories()
    print(f"Extracted {len(cats)} GrabFood Phnom Penh food categories!")
    out_path = Path("data/scraped/grabfood_categories.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if cats:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(cats[0].keys()))
            writer.writeheader()
            writer.writerows(cats)
        print(f"Saved to {out_path}")
        for c in cats[:4]:
            print(f"- {c['name']} ({c['dish_kh']}) | URL: {c['source_url']}")

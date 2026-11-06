"""
FoodChow Phnom Penh Scraper
Source: https://www.foodchow.com/en/Cambodia/Restaurants-in-Phnom-Penh/phnom-penh-restaurants
Extracts: restaurant names, ratings, cuisines, dining options, descriptions, and city areas.
"""

import re
import csv
import logging
from pathlib import Path
from bs4 import BeautifulSoup
import requests

logger = logging.getLogger(__name__)

URL = "https://www.foodchow.com/en/Cambodia/Restaurants-in-Phnom-Penh/phnom-penh-restaurants"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_text(s: str) -> str:
    return " ".join(s.split()).strip() if s else ""

def scrape_foodchow() -> list[dict]:
    print(f"Fetching FoodChow Phnom Penh: {URL}")
    r = requests.get(URL, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    rows = []
    seen_names = set()

    # Search for all links that link to the Phnom Penh page or restaurant cards
    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True))
        if "★" in text:
            # Pattern like "P Phnom Penh Spice Kitchen ★ 4.6 Regional & North Indian · Phnom Penh Popular Delivery"
            # Or "Urban Tadka ★ 4.5 Multi-Cuisine & Grill · Phnom Penh"
            m = re.search(r"^(?:[A-Z]\s+)?(?P<name>.+?)\s*★\s*(?P<rating>\d+\.\d+)\s*(?P<details>.*)$", text)
            if m:
                name = clean_text(m.group("name"))
                rating = m.group("rating")
                details = clean_text(m.group("details"))

                if name in seen_names or len(name) < 3:
                    continue

                # Details usually has: "Cuisine · City Tags"
                cuisine, tags_list = "", ["restaurant", "foodchow"]
                if "·" in details:
                    parts = details.split("·")
                    cuisine = clean_text(parts[0])
                    rest = clean_text(" ".join(parts[1:]))
                    for w in rest.split():
                        if w.lower() not in ["phnom", "penh", "·"]:
                            tags_list.append(w.lower())
                else:
                    cuisine = details

                if cuisine:
                    tags_list.append(cuisine.lower())

                seen_names.add(name)
                rows.append({
                    "id": f"foodchow-{len(rows)+1:04d}",
                    "name": name,
                    "dish_en": cuisine,
                    "dish_kh": "",
                    "description": f"{cuisine} restaurant listed on FoodChow Phnom Penh.",
                    "tags": ";".join(dict.fromkeys(tags_list)),
                    "price_usd": "",
                    "area": "Phnom Penh",
                    "lat": "",  # facts only: not given by the source, so left empty (never a default)
                    "lng": "",
                    "rating": rating,
                    "open_hour": "",
                    "close_hour": "",
                    "source": "foodchow",
                    "source_url": URL,
                    "date": "2026-11-04",
                    "image_path": "",
                    "phone_public": "",
                    "page_url": URL,
                })

    # Also capture featured cuisine specials if present
    specials = soup.find_all(text=re.compile(r"Best in Phnom Penh", re.I))
    for sp in specials:
        parent = sp.find_parent(["div", "section", "p", "a"])
        if parent:
            text = clean_text(parent.get_text(" ", strip=True))
            m = re.search(r"Best in Phnom Penh\s+([A-Za-z\s&]+?)\s+(A wholesome.*|Hot, crunchy.*|Slow-simmered.*|Iconic.*)", text)
            if m:
                category = clean_text(m.group(1))
                desc = clean_text(m.group(2))
                name = f"Phnom Penh {category}"
                if name not in seen_names:
                    seen_names.add(name)
                    rows.append({
                        "id": f"foodchow-{len(rows)+1:04d}",
                        "name": name,
                        "dish_en": category,
                        "dish_kh": "",
                        "description": desc,
                        "tags": "foodchow;cuisine_special",
                        "price_usd": "",
                        "area": "Phnom Penh",
                        "lat": "",  # facts only: not given by the source, so left empty (never a default)
                        "lng": "",
                        "rating": "",
                        "open_hour": "",
                        "close_hour": "",
                        "source": "foodchow",
                        "source_url": URL,
                        "date": "2026-11-04",
                        "image_path": "",
                        "phone_public": "",
                        "page_url": URL,
                    })

    return rows

if __name__ == "__main__":
    print("Scraping FoodChow Phnom Penh...")
    places = scrape_foodchow()
    print(f"Scraped {len(places)} listings from FoodChow!")
    out_path = Path("data/scraped/foodchow_places.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if places:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(places[0].keys()))
            writer.writeheader()
            writer.writerows(places)
        print(f"Saved to {out_path}")
        for p in places:
            print(f"- {p['name']} | Rating: {p['rating']} | Cuisine: {p['dish_en']}")

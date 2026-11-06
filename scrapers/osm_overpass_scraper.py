"""
OpenStreetMap Overpass API Scraper for Phnom Penh Food Venues
Source: https://overpass-api.de/api/interpreter
Extracts: restaurants, cafes, bakeries, fast food, street food across all 14 Khans of Phnom Penh
with coordinates, opening hours, Khmer and English bilingual names, phone numbers, and websites.
"""

import re
import csv
import json
import logging
from pathlib import Path
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_AMENITIES = "restaurant|cafe|fast_food|food_court|ice_cream|bar|pub"
OSM_SHOPS = "bakery|pastry|coffee|tea|confectionery"

OSM_QUERY = f"""[out:json][timeout:120];
rel["boundary"="administrative"]["admin_level"="4"]["name:en"="Phnom Penh"];
map_to_area->.pp;
rel(area.pp)["boundary"="administrative"]["admin_level"="6"];
map_to_area->.khans;
(
  nwr(area.pp)["amenity"~"^({OSM_AMENITIES})$"];
  nwr(area.pp)["shop"~"^({OSM_SHOPS})$"];
);
out center tags;"""

KHMER_RE = re.compile(r"[\u1780-\u17FF\u19E0-\u19FF]+")

CUISINE_MAP = {
    "khmer": ("khmer food", "ម្ហូបខ្មែរ"),
    "cambodian": ("khmer food", "ម្ហូបខ្មែរ"),
    "regional": ("khmer food", "ម្ហូបខ្មែរ"),
    "coffee": ("coffee", "កាហ្វេ"),
    "coffee_shop": ("coffee", "កាហ្វេ"),
    "bubble_tea": ("bubble tea", "តែគុជ"),
    "tea": ("tea", "តែ"),
    "noodle": ("noodles", "មី"),
    "noodles": ("noodles", "មី"),
    "bbq": ("bbq", "សាច់អាំង"),
    "barbecue": ("bbq", "សាច់អាំង"),
    "chinese": ("chinese food", "ម្ហូបចិន"),
    "japanese": ("japanese food", "ម្ហូបជប៉ុន"),
    "korean": ("korean food", "ម្ហូបកូរ៉េ"),
    "thai": ("thai food", "ម្ហូបថៃ"),
    "vietnamese": ("vietnamese food", "ម្ហូបវៀតណាម"),
    "french": ("french food", "ម្ហូបបារាំង"),
    "italian": ("italian food", "ម្ហូបអ៊ីតាលី"),
    "pizza": ("pizza", "ភីហ្សា"),
    "burger": ("burger", "ប៊ឺហ្គឺ"),
    "bakery": ("bakery", "នំប៉័ង"),
    "vegetarian": ("vegetarian food", "ម្ហូបបួស"),
    "indian": ("indian food", "ម្ហូបឥណ្ឌា"),
    "western": ("western food", "ម្ហូបអឺរ៉ុប"),
    "seafood": ("seafood", "គ្រឿងសមុទ្រ"),
    "ice_cream": ("ice cream", "ការ៉េម"),
    "fast_food": ("fast food", "អាហាររហ័ស"),
    "buffet": ("buffet", "អាហារប៊ូហ្វេ"),
}

AMENITY_KH = {
    "restaurant": ("restaurant", "ភោជនីយដ្ឋាន"),
    "cafe": ("cafe", "ហាងកាហ្វេ"),
    "fast_food": ("fast food", "អាហាររហ័ស"),
    "food_court": ("food court", "តូបអាហារ"),
    "ice_cream": ("ice cream", "ការ៉េម"),
    "bar": ("bar", "បារ"),
    "pub": ("pub", "ផាប់"),
    "bakery": ("bakery", "ហាងនំប៉័ង"),
}

def parse_time_float(t_str: str) -> float | None:
    m = re.search(r"(\d{1,2}):(\d{2})", t_str)
    if not m:
        return None
    return round(int(m.group(1)) + int(m.group(2)) / 60.0, 1)

def parse_osm_hours(h_str: str):
    if not h_str or h_str == "24/7":
        return (0.0, 24.0) if h_str == "24/7" else (None, None)
    m = re.search(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", h_str)
    if m:
        return parse_time_float(m.group(1)), parse_time_float(m.group(2))
    return None, None

def clean_text(s: str) -> str:
    return " ".join(s.split()).strip() if s else ""

def osm_element_to_row(elem: dict, khan: str) -> dict | None:
    tags = elem.get("tags", {})
    raw_name = clean_text(tags.get("name") or "")
    name_en = clean_text(tags.get("name:en") or "")
    name_kh = clean_text(tags.get("name:km") or "")

    if not raw_name and not name_en and not name_kh:
        return None

    # Detect Khmer name from raw name if not explicitly tagged
    if not name_kh and KHMER_RE.search(raw_name):
        name_kh = raw_name
    if not name_en and not KHMER_RE.search(raw_name):
        name_en = raw_name

    # Construct bilingual display name: e.g. "Brown Coffee (ប្រោន កាហ្វេ)" or whatever is available
    if name_en and name_kh and name_en != name_kh:
        display_name = f"{name_en} ({name_kh})"
    else:
        display_name = name_en or name_kh or raw_name

    # Coordinates
    lat = elem.get("lat") or (elem.get("center", {}).get("lat"))
    lng = elem.get("lon") or (elem.get("center", {}).get("lon"))
    if not lat or not lng:
        return None

    # Amenity and cuisines
    amenity_raw = tags.get("amenity") or tags.get("shop") or "restaurant"
    amenity_en, amenity_kh = AMENITY_KH.get(amenity_raw, ("restaurant", "ភោជនីយដ្ឋាន"))

    cuisine_tag = tags.get("cuisine", "").lower()
    dish_en_parts, dish_kh_parts = [], []
    tag_list = [amenity_en, amenity_kh]

    for c in re.split(r"[;,/]", cuisine_tag):
        c = c.strip()
        if c in CUISINE_MAP:
            c_en, c_kh = CUISINE_MAP[c]
            dish_en_parts.append(c_en)
            dish_kh_parts.append(c_kh)
            tag_list.extend([c_en, c_kh])
        elif c:
            dish_en_parts.append(f"{c} food")
            tag_list.append(c)

    # Fallback dish based on amenity
    if not dish_en_parts:
        if amenity_raw in ["cafe", "coffee"]:
            dish_en_parts.append("coffee")
            dish_kh_parts.append("កាហ្វេ")
        elif amenity_raw in ["bakery", "pastry"]:
            dish_en_parts.append("bakery")
            dish_kh_parts.append("នំប៉័ង")
        elif amenity_raw in ["ice_cream"]:
            dish_en_parts.append("ice cream")
            dish_kh_parts.append("ការ៉េម")

    dish_en = "; ".join(dict.fromkeys(dish_en_parts))
    dish_kh = " ".join(dict.fromkeys(dish_kh_parts))

    # Hours
    open_h, close_h = parse_osm_hours(tags.get("opening_hours", ""))

    # Contact
    phone = clean_text((tags.get("contact:phone") or tags.get("phone") or tags.get("contact:mobile") or "").split(";")[0])
    fb = (tags.get("contact:facebook") or tags.get("facebook") or "").strip()
    if fb and not fb.startswith("http"):
        fb = f"https://www.facebook.com/{fb.strip('/@ ')}"
    website = (tags.get("contact:website") or tags.get("website") or "").strip()
    page_url = fb or website

    osm_id = f"osm-{elem.get('type', 'node')[0]}{elem.get('id')}"
    osm_url = f"https://www.openstreetmap.org/{elem.get('type', 'node')}/{elem.get('id')}"

    # Area / Khan
    area_name = khan or tags.get("addr:district") or "Phnom Penh"
    street = tags.get("addr:street") or ""

    # Bilingual description
    desc_en = f"{amenity_en.capitalize()} in {area_name}, Phnom Penh."
    desc_kh = f"{amenity_kh}នៅខណ្ឌ {area_name} រាជធានីភ្នំពេញ។"
    if street:
        desc_en += f" Located on {street}."
    if name_kh and name_kh != display_name:
        desc_en += f" Khmer name: {name_kh}."

    description = f"{desc_en} {desc_kh}"

    return {
        "id": osm_id,
        "name": display_name,
        "dish_en": dish_en,
        "dish_kh": dish_kh,
        "description": description,
        "tags": ";".join(dict.fromkeys([t for t in tag_list if t])),
        "price_usd": "",
        "area": area_name,
        "lat": str(lat),
        "lng": str(lng),
        "rating": "",
        "open_hour": open_h if open_h is not None else "",
        "close_hour": close_h if close_h is not None else "",
        "source": "openstreetmap",
        "source_url": osm_url,
        "date": "2026-11-04",
        "image_path": "",
        "phone_public": phone,
        "page_url": page_url,
    }

def scrape_osm_overpass(cache_path: str = "data/raw/osm_phnom_penh.json") -> list[dict]:
    p = Path(cache_path)
    if p.exists() and p.stat().st_size > 1000:
        print(f"Loading cached OSM Overpass data from {p}...")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        print("Querying Overpass API for Phnom Penh food places...")
        headers = {"User-Agent": "CambodianFoodSearch/1.0"}
        r = requests.post(OVERPASS_URL, data={"data": OSM_QUERY}, headers=headers, timeout=120)
        r.raise_for_status()
        data = r.json()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f)
        print(f"Cached OSM response to {p}")

    elements = data if isinstance(data, list) else data.get("elements", [])
    rows = []
    seen = set()
    current_khan = ""

    for el in elements:
        if el.get("type") == "area":
            t = el.get("tags", {})
            if t.get("admin_level") == "6":
                current_khan = re.sub(r"^Khan\s+", "", t.get("name:en", "")).strip()
            continue

        row = osm_element_to_row(el, current_khan)
        if row and row["name"] and row["id"] not in seen:
            seen.add(row["id"])
            rows.append(row)

    return rows

if __name__ == "__main__":
    places = scrape_osm_overpass()
    print(f"Scraped {len(places)} bilingual food venues from OpenStreetMap Overpass across Phnom Penh!")
    out_path = Path("data/scraped/osm_places.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if places:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(places[0].keys()))
            writer.writeheader()
            writer.writerows(places)
        print(f"Saved to {out_path}")
        print("Sample bilingual OSM places:")
        for r in places[:4]:
            print(f"- {r['name']} | Area: {r['area']} | Dish: {r['dish_en']} ({r['dish_kh']}) | Phone: {r['phone_public']}")

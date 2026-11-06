"""
Cambodia Yellow Pages Scraper (Nationwide Coverage)
Source: https://cambodiayp.com/category/Restaurants
Extracts: restaurants across major cities and provinces of Cambodia:
Siem Reap, Sihanoukville, Battambang, Kampot, Kampong Cham, Phnom Penh, etc.
with exact Google Maps coordinates, phone numbers, addresses, working hours,
and conversational ordering/reservation instructions.
"""

import re
import csv
import time
import logging
from pathlib import Path
from bs4 import BeautifulSoup
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://cambodiayp.com"

MAJOR_CITIES = [
    ("Phnom Penh", "city:Phnom_Penh"),
    ("Siem Reap", "city:Siem_Reap"),
    ("Sihanoukville", "city:Sihanoukville"),
    ("Battambang", "city:Battambang"),
    ("Kampot", "city:Kampot"),
    ("Kampong Cham", "city:Kampong_Cham"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def clean_text(s: str) -> str:
    return " ".join(s.split()).strip() if s else ""

def parse_time_float(t_str: str) -> float | None:
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t_str, re.I)
    if not m:
        return None
    hr = int(m.group(1))
    mn = int(m.group(2) or 0)
    ampm = (m.group(3) or "").lower()
    if ampm == "pm" and hr < 12:
        hr += 12
    elif ampm == "am" and hr == 12:
        hr = 0
    return round(hr + mn / 60.0, 1)

def parse_detail_page(detail_url: str, session: requests.Session) -> dict:
    info = {
        "phone": "", "website": "", "lat": "", "lng": "",
        "open_hour": "", "close_hour": "", "description": "", "tags": []
    }
    try:
        r = session.get(detail_url, headers=HEADERS, timeout=8)
        if r.status_code != 200:
            return info
        soup = BeautifulSoup(r.text, "html.parser")

        # Phone
        tel_link = soup.find("a", href=lambda h: h and h.startswith("tel:"))
        if tel_link:
            info["phone"] = clean_text(tel_link.get_text())

        # Website & Maps GPS
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if "google.com/maps" in href:
                m = re.search(r"daddr=([\d.]+),([\d.]+)", href)
                if m:
                    info["lat"], info["lng"] = m.group(1), m.group(2)
            elif href.startswith("http") and not any(d in href for d in ["cambodiayp", "woomar", "facebook", "twitter", "google", "schema.org"]):
                if not info["website"]:
                    info["website"] = href

        # Categories
        cat_links = soup.select("a[href*='/category/']")
        info["tags"] = list(dict.fromkeys([clean_text(c.get_text()).lower() for c in cat_links if clean_text(c.get_text())]))

        # Description
        for div in soup.select(".desc, .description, .details, .text"):
            t = clean_text(div.get_text())
            if "Company description" in t:
                desc = t.replace("Company description", "").strip()
                if len(desc) > len(info["description"]):
                    info["description"] = desc

        # Hours
        hours_text = ""
        for div in soup.select(".info, .details, .text"):
            t = clean_text(div.get_text())
            if "Working hours" in t:
                hours_text = t
                break
        if hours_text:
            m = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s*(?:to|-)\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM))", hours_text, re.I)
            if m:
                info["open_hour"] = parse_time_float(m.group(1)) or ""
                info["close_hour"] = parse_time_float(m.group(2)) or ""

    except Exception as e:
        logger.warning(f"Error fetching detail {detail_url}: {e}")

    return info

def scrape_yellowpages_nationwide(cities: list = None, pages_per_city: int = 1, fetch_details: bool = True) -> list[dict]:
    if cities is None:
        cities = MAJOR_CITIES

    session = requests.Session()
    places = []
    seen_ids = set()

    for city_name, city_param in cities:
        print(f"\n--- Scraping Yellow Pages for {city_name} ---")
        for page in range(1, pages_per_city + 1):
            url = f"{BASE_URL}/category/Restaurants/{city_param}" if page == 1 else f"{BASE_URL}/category/Restaurants/{page}/{city_param}"
            print(f"Fetching {city_name} page {page}: {url}")
            try:
                r = session.get(url, headers=HEADERS, timeout=12)
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, "html.parser")
                companies = soup.select(".company")
                if not companies:
                    break

                for c in companies:
                    name_el = c.select_one("h4, h3, a")
                    if not name_el:
                        continue
                    name = clean_text(name_el.get_text())
                    if not name or name in seen_ids:
                        continue

                    link_el = name_el if name_el.name == "a" else name_el.find("a")
                    rel_url = link_el["href"] if link_el and "href" in link_el.attrs else ""
                    detail_url = f"{BASE_URL}{rel_url}" if rel_url.startswith("/") else rel_url

                    addr_el = c.select_one(".address, .location")
                    address = clean_text(addr_el.get_text()) if addr_el else ""

                    phone_el = c.select_one(".phone, [class*='phone']")
                    phone = clean_text(phone_el.get_text()) if phone_el else ""

                    lat, lng, open_h, close_h, desc, website, detail_tags = "", "", "", "", "", "", []
                    if fetch_details and detail_url:
                        time.sleep(0.3)
                        det = parse_detail_page(detail_url, session)
                        phone = phone or det["phone"]
                        website = det["website"]
                        lat, lng = det["lat"], det["lng"]
                        open_h, close_h = det["open_hour"], det["close_hour"]
                        desc = det["description"]
                        detail_tags = det["tags"]

                    # Conversational instructions
                    desc_parts = []
                    if desc:
                        desc_parts.append(desc)
                    else:
                        desc_parts.append(f"Restaurant located in {city_name}, Cambodia. ភោជនីយដ្ឋាននៅ{city_name}។")

                    if address:
                        desc_parts.append(f"Address: {address}.")
                    if phone:
                        desc_parts.append(f"How to contact: Call {phone} for table reservations and takeaway. ទូរស័ព្ទកក់តុ៖ {phone}។")
                    if website:
                        desc_parts.append(f"Website / Online menu: {website}.")

                    tags = ["restaurant", city_name.lower().replace(" ", "_")]
                    if detail_tags:
                        tags.extend(detail_tags)

                    seen_ids.add(name)
                    places.append({
                        "id": f"yp-{len(places)+1:04d}",
                        "name": name,
                        "dish_en": "",
                        "dish_kh": "",
                        "description": " ".join(desc_parts),
                        "tags": ";".join(dict.fromkeys(tags)),
                        "price_usd": "",  # facts only: not given by the source, so left empty (never a default)
                        "area": city_name,
                        "lat": lat,
                        "lng": lng,
                        "rating": "",  # facts only: not given by the source, so left empty (never a default)
                        "open_hour": open_h or "",  # facts only: not given by the source, so left empty (never a default)
                        "close_hour": close_h or "",
                        "source": "yellowpages-cambodia",
                        "source_url": detail_url or url,
                        "date": "2026-11-05",
                        "image_path": "",
                        "phone_public": phone,
                        "page_url": website,
                        "address_raw": address,
                    })

            except Exception as e:
                print(f"Error scraping {city_name} page {page}: {e}")
                break

    return places

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scrape Cambodia Yellow Pages nationwide")
    parser.add_argument("--pages", type=int, default=1, help="Pages per city")
    parser.add_argument("--output", type=str, default="data/scraped/yellowpages_places.csv", help="Output path")
    args = parser.parse_args()

    places = scrape_yellowpages_nationwide(pages_per_city=args.pages, fetch_details=True)
    print(f"\nScraped {len(places)} restaurants nationwide from Cambodia Yellow Pages!")
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if places:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(places[0].keys()))
            writer.writeheader()
            writer.writerows(places)
        print(f"Saved to {out_path}")
        print("Sample nationwide rows:")
        for p in places[:5]:
            print(f"- {p['name']} | Area: {p['area']} | Phone: {p['phone_public']} | Lat/Lng: {p['lat']},{p['lng']}")

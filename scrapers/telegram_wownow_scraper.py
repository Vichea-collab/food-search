"""
WOWNOW Deals Telegram Channel Scraper (Nationwide Multi-Page)
Source: https://t.me/s/wownow_fooddelivery
Extracts: vendor name, dish/combo name (Khmer & English), price (USD/KHR),
promotions, image URLs, and ordering links with deep pagination.
"""

import re
import csv
import logging
from pathlib import Path
from bs4 import BeautifulSoup
import requests
try:                               # scrapers/robots.py: obey robots.txt and the site's crawl delay
    from scrapers import robots
except ImportError:
    import robots

logger = logging.getLogger(__name__)

CHANNEL_URL = "https://t.me/s/wownow_fooddelivery"

KHMER_DIGITS = str.maketrans("០១២៣៤៥៦៧៨៩", "0123456789")
PRICE_RE = re.compile(
    r"(?P<usd1>\$\s*\d+(?:[.,]\d{1,2})?)"                                    # $2.50
    r"|(?P<usd2>\d+(?:[.,]\d{1,2})?\s*(?:\$|usd\b|ដុល្លារ))"                 # 2.50$
    r"|(?P<khr>(?:\d{1,3}(?:[.,]\d{3})+|\d{3,6})\s*(?:៛|រៀល|riel\b|khr\b))",  # 8000៛
    re.I
)
KHMER_CHAR_RE = re.compile(r"[\u1780-\u17FF\u19E0-\u19FF]")

KNOWN_BRANDS = [
    "TUBE Coffee", "Texas Chicken", "Domino's Pizza", "Pong Cambodia", "KFC",
    "MIXUE", "Koi The", "Brown Coffee", "Amazon Cafe", "Starbucks", "Lotteria",
    "The Pizza Company", "Burger King", "Carl's Jr", "Auntie Anne's", "Dunkin'",
    "BreadTalk", "Tous Les Jours", "Chatime", "Dakasi", "Gong Cha", "An Cha",
    "Habit Burger", "Dairy Queen", "Krispy Kreme", "Pizza Hut", "Papa John's",
    "Kuy Teav", "Bay Sach Chrouk", "Lok Lak", "BonChon"
]

def parse_price(text: str) -> tuple[str, str]:
    """Return (usd_price, original_price_str)."""
    text_clean = text.translate(KHMER_DIGITS)
    m = PRICE_RE.search(text_clean)
    if not m:
        # Check discount %
        disc_m = re.search(r"(\d{1,2})%\s*(?:off|ចុះ|បញ្ចុះ)", text, re.I)
        if disc_m:
            return "", f"{disc_m.group(1)}% off"
        return "", ""
    if m.group("usd1"):
        val = re.sub(r"[^\d.]", "", m.group("usd1"))
        return f"{float(val):.2f}" if val else "", f"${val}"
    elif m.group("usd2"):
        val = re.sub(r"[^\d.]", "", m.group("usd2"))
        return f"{float(val):.2f}" if val else "", f"${val}"
    elif m.group("khr"):
        val = re.sub(r"[^\d]", "", m.group("khr"))
        if val:
            usd = round(float(val) / 4100.0, 2)
            return f"{usd:.2f}" if usd > 0 else "", f"{val}៛"
    return "", ""

def extract_brand(text: str) -> str:
    for b in KNOWN_BRANDS:
        if re.search(rf"\b{re.escape(b)}\b", text, re.I):
            return b
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if lines:
        first = clean_fancy_chars(lines[0])
        m = re.match(r"^([A-Za-z0-9\s'&]+?)(?:\s+\d+|\s+off|\s+on|\s+combo|\s+deal|\s+special|\s+promo)", first, re.I)
        if m and len(m.group(1).strip()) > 2:
            return m.group(1).strip()
        if len(first.split()) <= 4:
            return first
    return "WOWNOW Merchant"

def clean_fancy_chars(s: str) -> str:
    res = []
    for char in s:
        cp = ord(char)
        if 0x1D400 <= cp <= 0x1D419:
            res.append(chr(cp - 0x1D400 + 65))
        elif 0x1D41A <= cp <= 0x1D433:
            res.append(chr(cp - 0x1D41A + 97))
        elif 0x1D5D4 <= cp <= 0x1D5ED:
            res.append(chr(cp - 0x1D5D4 + 65))
        elif 0x1D5EE <= cp <= 0x1D607:
            res.append(chr(cp - 0x1D5EE + 97))
        elif 0x1D7CE <= cp <= 0x1D7D7:
            res.append(chr(cp - 0x1D7CE + 48))
        elif 0x1D7EC <= cp <= 0x1D7F5:
            res.append(chr(cp - 0x1D7EC + 48))
        else:
            res.append(char)
    return "".join(res)

def scrape_wownow_telegram(max_pages: int = 5, limit_deals: int = 100) -> list[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    rows = []
    seen_ids = set()
    before_id = None

    for page in range(max_pages):
        url = f"{CHANNEL_URL}?before={before_id}" if before_id else CHANNEL_URL
        print(f"Fetching WOWNOW Telegram page {page + 1}: {url}")
        res = robots.get(url, headers=headers, timeout=15, min_pause=0.5)
        soup = BeautifulSoup(res.text, "html.parser")
        wraps = soup.select(".tgme_widget_message_wrap")
        if not wraps:
            break

        # earliest post on this page for pagination
        first_msg = wraps[0].select_one(".tgme_widget_message")
        if not first_msg:
            break
        before_id = first_msg["data-post"].split("/")[-1]

        for p in wraps:
            msg_el = p.select_one(".tgme_widget_message")
            msg_id = msg_el.get("data-post", "") if msg_el else ""
            if not msg_id or msg_id in seen_ids:
                continue

            text_el = p.select_one(".tgme_widget_message_text")
            if not text_el:
                continue
            raw_text = text_el.get_text("\n", strip=True)
            norm_text = clean_fancy_chars(raw_text)

            photo_el = p.select_one(".tgme_widget_message_photo_wrap")
            photo_url = ""
            if photo_el and "style" in photo_el.attrs:
                m = re.search(r"background-image:url\('([^']+)'\)", photo_el["style"])
                if m:
                    photo_url = m.group(1)

            time_el = p.select_one("time")
            date_str = ""
            if time_el and "datetime" in time_el.attrs:
                date_str = time_el["datetime"].split("T")[0]

            brand = extract_brand(norm_text)
            price_usd, price_display = parse_price(norm_text)

            lines = [line.strip() for line in norm_text.split("\n") if line.strip()]
            khmer_lines = [l for l in lines if KHMER_CHAR_RE.search(l)]
            en_lines = [l for l in lines if not KHMER_CHAR_RE.search(l) and len(l) > 2]

            dish_en = en_lines[0] if en_lines else brand
            dish_kh = khmer_lines[0] if khmer_lines else ""

            # Conversational description with price, ordering, and delivery instructions
            desc_parts = [f"Promotional food offer for {brand}."]
            if price_display:
                desc_parts.append(f"Price: {price_display}. តម្លៃ: {price_display}។")
            desc_parts.append(f"How to order: Order via WOWNOW Food Delivery app. Delivery available across Cambodia. អាចកុម្ម៉ង់ដឹកជញ្ជូនតាមអេប WOWNOW។")
            if lines:
                desc_parts.append("Details: " + " ".join(lines[:2]))

            tags = ["wownow", "delivery", "promotion", "deals"]
            lower_all = norm_text.lower()
            if "coffee" in lower_all or "tea" in lower_all or "drink" in lower_all:
                tags.append("beverage")
            if "pizza" in lower_all:
                tags.append("pizza")
            if "burger" in lower_all or "chicken" in lower_all:
                tags.append("fast_food")

            seen_ids.add(msg_id)
            rows.append({
                "id": f"wownow-tg-{msg_id.split('/')[-1]}",
                "name": brand,
                "dish_en": dish_en,
                "dish_kh": dish_kh,
                "description": " ".join(desc_parts),
                "tags": ";".join(dict.fromkeys(tags)),
                "price_usd": price_usd,
                "area": "",  # facts only: not given by the source, so left empty (never a default)
                "lat": "",
                "lng": "",
                "rating": "",
                "open_hour": "",
                "close_hour": "",
                "source": "wownow-telegram",
                "source_url": f"https://t.me/{msg_id}",
                "date": date_str or "2026-11-05",
                "image_url": photo_url,
                "image_path": photo_url,
                "phone_public": "",
                "page_url": "https://www.wownow-kh.com/",
            })

            if len(rows) >= limit_deals:
                break
        
        if len(rows) >= limit_deals:
            break

    return rows

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scrape WOWNOW Telegram food deals")
    parser.add_argument("--pages", type=int, default=10, help="Max telegram pagination pages")
    parser.add_argument("--limit", type=int, default=200, help="Max deals to collect")
    parser.add_argument("--output", type=str, default="data/scraped/wownow_deals.csv", help="Output CSV path")
    args = parser.parse_args()

    deals = scrape_wownow_telegram(max_pages=args.pages, limit_deals=args.limit)
    print(f"Scraped {len(deals)} food promotions with prices from WOWNOW Telegram!")
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if deals:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(deals[0].keys()))
            writer.writeheader()
            writer.writerows(deals)
        print(f"Saved to {out_path}")
        print("Sample deals with price & ordering:")
        for d in deals[:4]:
            print(f"- {d['name']} | Price: ${d['price_usd']} | Dish: {d['dish_en']} | Img: {bool(d['image_path'])}")

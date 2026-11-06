"""
Canby Publications Scraper for Phnom Penh Restaurants
Source: https://canbypublications.com/phnompenh/pprest.htm
Extracts: name, cuisine, description, hours, phone, address, website, inferred area.
"""

import re
import csv
import logging
from pathlib import Path
from bs4 import BeautifulSoup
import requests

logger = logging.getLogger(__name__)

CANBY_URL = "https://canbypublications.com/phnompenh/pprest.htm"

AREA_PATTERNS = [
    (re.compile(r"bkk1|bkk\s*1|boeung\s*keng\s*kang|boeng\s*keng\s*kang|st\s*51|pasteur|st\s*278|st\s*302|st\s*306|st\s*288|st\s*294|st\s*352|st\s*360", re.I), "Boeung Keng Kang"),
    (re.compile(r"toul\s*tom\s*poung|russian\s*market|st\s*432|st\s*450|st\s*440|st\s*155|st\s*456|st\s*460|chamkar\s*mon|bassac\s*lane|tonle\s*bassac|st\s*308", re.I), "Chamkar Mon"),
    (re.compile(r"sisowath\s*quay|riverfront|st\s*178|st\s*240|st\s*136|st\s*108|st\s*110|st\s*130|st\s*144|st\s*118|st\s*154|st\s*184|st\s*172|st\s*174|wat\s*phnom|daun\s*penh|riverside|kandal\s*market|psar\s*chas", re.I), "Daun Penh"),
    (re.compile(r"toul\s*kork|st\s*315|st\s*289|st\s*516|st\s*528|st\s*592|st\s*337", re.I), "Toul Kork"),
    (re.compile(r"chroy\s*changvar|chroy\s*changva", re.I), "Chroy Changvar"),
    (re.compile(r"7\s*makara|prampei\s*makara|prampir\s*makara|st\s*214|st\s*169|olympic|st\s*111", re.I), "Prampir Makara"),
    (re.compile(r"sen\s*sok|tk\s*avenue|aeon\s*2", re.I), "Sen Sok"),
    (re.compile(r"me\s*anchey|aeon\s*3|steung\s*mean\s*chey", re.I), "Mean Chey"),
]

CUISINE_MAP = {
    "american": ("american food", "អាហារអាមេរិក"),
    "british": ("british food", "ម្ហូបអង់គ្លេស"),
    "buffets": ("buffet", "អាហារប៊ូហ្វេ"),
    "cambodian": ("khmer food", "ម្ហូបខ្មែរ"),
    "chinese": ("chinese food", "ម្ហូបចិន"),
    "french": ("french food", "ម្ហូបបារាំង"),
    "indian": ("indian food", "ម្ហូបឥណ្ឌា"),
    "italian": ("italian food", "ម្ហូបអ៊ីតាលី"),
    "japanese": ("japanese food", "ម្ហូបជប៉ុន"),
    "korean": ("korean food", "ម្ហូបកូរ៉េ"),
    "mexican": ("mexican food", "ម្ហូបម៉ិកស៊ិក"),
    "thai": ("thai food", "ម្ហូបថៃ"),
    "vietnamese": ("vietnamese food", "ម្ហូបវៀតណាម"),
    "vegetarian": ("vegetarian food", "ម្ហូបបួស"),
    "seafood": ("seafood", "គ្រឿងសមុទ្រ"),
}

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("Â’", "'").replace("Â“", '"').replace("Â”", '"').replace("Â–", "-").replace("Â—", "-")
    text = text.replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return " ".join(text.split())

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

def parse_hours(text: str):
    m = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)\s*[-–—to]+\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM))", text, re.I)
    if not m:
        return None, None
    op = parse_time_float(m.group(1))
    cl = parse_time_float(m.group(2))
    return op, cl

def infer_area(text: str) -> str:
    for pat, area in AREA_PATTERNS:
        if pat.search(text):
            return area
    return "Phnom Penh"

def scrape_canby(html_content: str = None) -> list[dict]:
    if html_content is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(CANBY_URL, headers=headers, timeout=20)
        # Use ISO-8859-1 decode with proper clean
        html_content = res.content.decode("iso-8859-1", errors="replace")

    soup = BeautifulSoup(html_content, "html.parser")
    rows = []
    seen_names = set()

    # Find leaf tables with cellspacing="7"
    leaf_tables = [t for t in soup.find_all("table") if len(t.find_all("table")) == 0 and t.get("cellspacing") == "7"]

    for table in leaf_tables:
        b_tag = table.find(["b", "strong"])
        if not b_tag:
            continue
        name = clean_text(b_tag.get_text(strip=True))
        if not name or len(name) < 2 or len(name) > 70 or name.endswith("..."):
            continue
        if name.lower() in ["dining", "phnom penh dining", "restaurants", "bars", "contents"]:
            continue
        if name in seen_names:
            continue

        rows_in_table = table.find_all("tr")
        r0 = rows_in_table[0] if len(rows_in_table) > 0 else table
        r1 = rows_in_table[1] if len(rows_in_table) > 1 else None

        info_text = clean_text(r0.get_text(" ", strip=True))
        addr_text = clean_text(r1.get_text(" ", strip=True)) if r1 else ""

        # Extract phone
        phone_m = re.search(r"Tel:\s*([\d\s\-/]+)", info_text)
        phone = ""
        if phone_m:
            phone = clean_text(phone_m.group(1)).replace(" ", "").replace("/", ";")

        # Extract hours
        open_h, close_h = parse_hours(info_text)

        # Extract website or facebook
        page_url = ""
        for a in table.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("http") and "canby" not in href:
                page_url = href
                break
        if not page_url:
            fb_m = re.search(r"Facebook:\s*([^\s\n,]+)", info_text)
            if fb_m:
                page_url = f"https://www.facebook.com/{fb_m.group(1).strip()}"

        # Detect cuisine
        cuisine_en, cuisine_kh = "", ""
        tags = ["restaurant"]
        for c_key, (c_en, c_kh) in CUISINE_MAP.items():
            if c_key in info_text.lower():
                cuisine_en, cuisine_kh = c_en, c_kh
                tags.append(c_key)
                break

        if "bar" in name.lower() or "bar" in info_text.lower():
            tags.append("bar")
        if "cafe" in name.lower() or "café" in name.lower() or "coffee" in info_text.lower():
            tags.append("cafe")
        if "buffet" in name.lower() or "buffet" in info_text.lower():
            tags.append("buffet")

        # Infer area
        combined_loc = f"{addr_text} {info_text}"
        area = infer_area(combined_loc)

        # Description
        desc = info_text
        # Remove name, phone, hours from description
        desc = desc.replace(name, "").strip()
        if phone_m:
            desc = desc.replace(phone_m.group(0), "").strip()
        desc = re.sub(r"\d{1,2}(?::\d{2})?\s*(?:AM|PM)?\s*[-–—to]+\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM)", "", desc).strip()
        desc = re.sub(r"Dining[-:\w\s/]*", "", desc).strip()
        desc = re.sub(r"Bar[-:\w\s/]*", "", desc).strip()
        desc = clean_text(desc).strip(" -—:\",")

        if not desc:
            desc = f"Restaurant in {area}, Phnom Penh."

        seen_names.add(name)
        rows.append({
            "id": f"canby-{len(rows)+1:04d}",
            "name": name,
            "dish_en": cuisine_en,
            "dish_kh": cuisine_kh,
            "description": desc,
            "tags": ";".join(dict.fromkeys(tags)),
            "price_usd": "",
            "area": area,
            "lat": "",
            "lng": "",
            "rating": "",
            "open_hour": open_h if open_h is not None else "",
            "close_hour": close_h if close_h is not None else "",
            "source": "canby-publications",
            "source_url": CANBY_URL,
            "date": "2026-11-04",
            "image_path": "",
            "phone_public": phone,
            "page_url": page_url,
            "address_raw": addr_text,
        })

    return rows

if __name__ == "__main__":
    print("Scraping Canby Publications Phnom Penh restaurants...")
    places = scrape_canby()
    print(f"Scraped {len(places)} places from Canby Publications!")
    out_path = Path("data/scraped/canby_places.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if places:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(places[0].keys()))
            writer.writeheader()
            writer.writerows(places)
        print(f"Saved to {out_path}")
        print("Sample rows:")
        for p in places[:5]:
            print(f"- {p['name']} | Area: {p['area']} | Hours: {p['open_hour']}-{p['close_hour']} | Phone: {p['phone_public']} | Link: {p['page_url']} | Addr: {p['address_raw']}")

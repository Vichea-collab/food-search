"""
Automated Khmer Food Image Harvester via Bing Search.

Collects authentic, high-resolution photos for the 10 most iconic Khmer dishes
that are missing from the Food-101 / khfood dataset.

Filters & Quality checks:
  - Valid image check via PIL
  - Minimum size: 240x240
  - Reasonable aspect ratio: 0.4 <= width/height <= 2.5
  - Perceptual hash deduplication (skips duplicates)
  - Saves in standard JPEG format to data/khfood/harvested/<dish_id>/
"""

import io
import json
import logging
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

from PIL import Image, ImageStat
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("khfood_harvester")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "khfood" / "harvested"

DISH_TARGETS = {
    "kh_amok_trey": {
        "name": "Fish Amok (amok trey)",
        "name_kh": "អាម៉ុកត្រី",
        "search": "amok trey fish amok",
        "queries": [
            "fish amok cambodia",
            "អាម៉ុកត្រី",
            "amok trey khmer food",
            "cambodian steamed fish amok curry",
        ],
    },
    "kh_kuy_teav": {
        "name": "Kuy teav noodle soup",
        "name_kh": "គុយទាវ",
        "search": "kuy teav noodle soup",
        "queries": [
            "kuy teav phnom penh",
            "គុយទាវភ្នំពេញ",
            "cambodian kuy teav noodle soup",
            "kuy teav sach ko khmer",
        ],
    },
    "kh_bai_sach_chrouk": {
        "name": "Bai sach chrouk (grilled pork broken rice)",
        "name_kh": "បាយសាច់ជ្រូក",
        "search": "bai sach chrouk pork rice",
        "queries": [
            "bai sach chrouk",
            "បាយសាច់ជ្រូក",
            "cambodian pork broken rice",
            "bai sach chrouk breakfast khmer",
        ],
    },
    "kh_lort_cha": {
        "name": "Lort cha (fried pin noodles)",
        "name_kh": "លតឆា",
        "search": "lort cha fried noodles",
        "queries": [
            "lort cha cambodia",
            "លតឆា",
            "khmer fried pin noodle",
            "lort cha sach ko",
        ],
    },
    "kh_bok_lhong": {
        "name": "Bok lhong (khmer papaya salad)",
        "name_kh": "បុកល្ហុង",
        "search": "bok lhong papaya salad",
        "queries": [
            "bok lhong cambodia",
            "បុកល្ហុង",
            "khmer papaya salad kdam seh",
            "bok lhong khmer street food",
        ],
    },
    "kh_num_pang": {
        "name": "Num pang (khmer baguette sandwich)",
        "name_kh": "នំប៉័ងប៉ាតេ",
        "search": "num pang pate sandwich",
        "queries": [
            "num pang cambodia",
            "នំប៉័ងប៉ាតេ",
            "cambodian baguette sandwich",
            "num pang sach chrouk",
        ],
    },
    "kh_sach_ko_ang": {
        "name": "Sach ko ang (lemongrass beef skewers)",
        "name_kh": "សាច់គោអាំង",
        "search": "sach ko ang beef skewers",
        "queries": [
            "sach ko ang cambodia",
            "សាច់គោអាំង",
            "khmer beef skewers kroeung",
            "cambodian beef skewers",
        ],
    },
    "kh_banh_chhev": {
        "name": "Banh chhev (crispy khmer crepe)",
        "name_kh": "បាញ់ឆែវ",
        "search": "banh chhev crispy crepe",
        "queries": [
            "banh chhev cambodia",
            "បាញ់ឆែវ",
            "cambodian crispy crepe turmeric",
            "khmer banh chhev",
        ],
    },
    "kh_borbor": {
        "name": "Borbor (khmer rice congee)",
        "name_kh": "បបរ",
        "search": "borbor rice porridge congee",
        "queries": [
            "borbor cambodia",
            "បបរគ្រឿង",
            "cambodian rice congee",
            "borbor sach moan khmer",
        ],
    },
    "kh_chha_kdao": {
        "name": "Chha kdao (spicy holy basil stir fry)",
        "name_kh": "ឆាក្តៅ",
        "search": "chha kdao stir fry",
        "queries": [
            "chha kdao cambodia",
            "ឆាក្តៅសាច់គោ",
            "khmer holy basil stir fry",
            "chha kdao sach moan",
        ],
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def tiny_hash(img: Image.Image) -> str:
    """Perceptual hash to avoid duplicate images."""
    small = img.convert("L").resize((8, 8))
    pixels = list(small.tobytes())
    avg = sum(pixels) / 64
    return "".join("1" if p > avg else "0" for p in pixels)


def fetch_bing_image_urls(query: str, max_urls: int = 50) -> list:
    urls = []
    sess = requests.Session()
    sess.headers.update(HEADERS)

    for first in range(1, max_urls + 20, 35):
        if len(urls) >= max_urls:
            break
        search_url = f"https://www.bing.com/images/search?q={quote_plus(query)}&first={first}"
        try:
            r = sess.get(search_url, timeout=10)
            if r.status_code == 200:
                found = re.findall(r'murl&quot;:&quot;(https?://[^&]+)&quot;', r.text)
                for u in found:
                    if u not in urls:
                        urls.append(u)
            time.sleep(1.0)
        except Exception as e:
            log.warning("Bing search failed for '%s' (first=%d): %s", query, first, e)
            break

    return urls[:max_urls]


def harvest(target_per_dish: int = 60):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    seen_hashes = set()
    total_saved = 0

    img_sess = requests.Session()
    img_sess.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "image/*,*/*;q=0.8",
    })

    for idx, (dish_id, info) in enumerate(DISH_TARGETS.items(), 1):
        dish_folder = OUT_DIR / dish_id
        dish_folder.mkdir(parents=True, exist_ok=True)

        existing = list(dish_folder.glob("*.jpg"))
        saved = len(existing)
        for f in existing:
            try:
                with Image.open(f) as im:
                    seen_hashes.add(tiny_hash(im))
            except Exception:
                pass

        log.info("[%d/%d] Harvesting %s (%s)... current count: %d (target: %d)",
                 idx, len(DISH_TARGETS), info["name"], dish_id, saved, target_per_dish)

        for q in info["queries"]:
            if saved >= target_per_dish:
                break

            needed = target_per_dish - saved
            urls = fetch_bing_image_urls(q, max_urls=min(50, needed * 2))
            log.info("  Query '%s' -> found %d image links", q, len(urls))

            for u in urls:
                if saved >= target_per_dish:
                    break
                try:
                    r = img_sess.get(u, timeout=6)
                    if r.status_code != 200 or len(r.content) < 5000:
                        continue

                    im = Image.open(io.BytesIO(r.content))
                    w, h = im.size
                    if w < 240 or h < 240:
                        continue

                    ratio = w / float(h)
                    if ratio < 0.45 or ratio > 2.4:
                        continue

                    th = tiny_hash(im)
                    if th in seen_hashes:
                        continue

                    seen_hashes.add(th)
                    im_rgb = im.convert("RGB")
                    out_file = dish_folder / f"{saved:04d}.jpg"
                    im_rgb.save(out_file, "JPEG", quality=90)
                    saved += 1
                    total_saved += 1
                except Exception:
                    continue

            time.sleep(1.0)

        log.info("  ✓ %s finished with %d photos", dish_id, saved)

    log.info("==================================================")
    log.info("Harvest complete: saved %d total photos in %s", total_saved, OUT_DIR)


if __name__ == "__main__":
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    harvest(target_per_dish=target)

"""
Harvest more photos of the 26 Khmer dishes the photo model knows, from sources that publish a LICENCE for every photo:

  Wikimedia Commons   files in the Cambodian-food categories (the category name is the label) + a text search
  Openverse           Creative-Commons photos (Flickr etc.); anonymous limit 20 requests/minute and 200/day
  Bing images         (--sources bing) the most photos, but NO licence: the record says "unknown (web image search)" and
                      keeps the page URL. For training a course model only; do not publish the photos. Bing's terms
                      do not allow automated use, so it is slow (2 s per request) and off by default.

Why not only web image search: a search result has no licence and often shows the wrong dish. Here every file is
recorded in data/khfood/harvest_sources.csv (dish, file, source, title, creator, licence, page URL) so the report
can credit it and a photo can be removed later.

A photo is kept only when ALL of these hold:
  * its own text (title / description / tags / category) names the dish: a "strong" word that only this dish has
    ("lok lak", "amok", "kuy teav") or a generic word ("papaya salad") together with Cambodia/Khmer;
  * it is a real photo: JPEG/PNG/WebP, short side >= 256 px, aspect ratio 0.45-2.4;
  * it is not a near-duplicate (8x8 difference hash, Hamming distance <= 4) of ANY photo already in
    data/khfood/combined, harvested or rejected, or of one saved earlier in this run
    (a duplicate in the test split would make the test score look better than it is).
Photos are saved at most 800 px on the long side to data/khfood/harvested/<dish_id>/ (cm_<pageid>.jpg, ov_<id>.jpg).
Run scrapers/clean_harvested_images.py --apply afterwards (CLIP food check: logos, people, menus, drawings).

Usage:
    venv/bin/python scrapers/harvest_khmer_open_images.py                    # all 26 dishes, both sources
    venv/bin/python scrapers/harvest_khmer_open_images.py --dishes kh_amok_trey,kh_kuy_teav --sources commons
Safe to run again: it only adds photos it does not have yet.
"""
import argparse
import csv
import hashlib
import html
import io
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("harvest")

ROOT = Path(__file__).resolve().parent.parent
KH = ROOT / "data" / "khfood"
OUT = KH / "harvested"
SOURCES_CSV = KH / "harvest_sources.csv"
CATEGORY_CACHE = KH / "commons_categories.json"
UA = "khmer-food-dataset-builder/1.0 (course project, image research)"      # a generic client name
CONTEXT = re.compile(r"cambodia|khmer|phnom penh|siem ?reap|kampot|battambang|sihanouk|kep\b|angkor|ខ្មែរ|កម្ពុជា|ភ្នំពេញ|សៀមរាប",
                     re.I)
MIN_SIDE, MAX_SIDE = 256, 800
MAX_WAIT = 120          # seconds: a longer Retry-After means "come back later", not worth waiting for

# dish_id -> strong: words only this dish has | generic: words that need Cambodia/Khmer next to them | queries | commons
# categories (a file in a category whose NAME matches `strong` gets the dish, whatever its title says)
D = {
    "kh_shrimp_salad": dict(strong=r"bongkea|bongkae|plea bong|ភ្លាបង្គា", generic=r"(shrimp|prawn)s?.{0,20}salad",
                            queries=["plea bongkea", "cambodian shrimp salad", "khmer raw shrimp salad"]),
    "kh_khor": dict(strong=r"\bkh?or\b.{0,15}(pork|sach)|sach chrouk ko|ខសាច់ជ្រូក", generic=r"(braised|caramel+is?ed|caramel) pork",
                    queries=["cambodian braised pork khor", "khmer caramelised pork", "sach chrouk khor"]),
    "kh_beef_stew": dict(strong=r"sach ko (kho|khor)|សាច់គោខ", generic=r"beef stew",
                         queries=["khmer beef stew", "sach ko kho cambodia", "cambodian beef stew"]),
    "kh_cha_kney": dict(strong=r"ch?ha k?hn?ey|cha kney|cha khnhey|ឆាខ្ញី", generic=r"ginger.{0,15}stir|stir.{0,15}ginger",
                        queries=["cha kney", "khmer ginger stir fry", "cambodian ginger chicken stir fry"]),
    "kh_salted_crab": dict(strong=r"kdam (prai|bai)|ក្តាមប្រៃ", generic=r"salted (field |rice )?crab",
                           queries=["kdam prai", "cambodian salted crab", "khmer salted crab"]),
    "kh_kari": dict(strong=r"samlor kari|kari sach|ការី", generic=r"(khmer|cambodian) (chicken )?curry|chicken curry",
                    queries=["khmer curry kari", "cambodian chicken curry", "samlor kari"]),
    "kh_lok_lak": dict(strong=r"lok[ -]?lak|lock[ -]?lak|ឡុកឡាក់", generic=r"$^",
                       queries=["lok lak", "loklak cambodia", "cambodian beef lok lak", "lok lak beef"]),
    "kh_num_banh_chok": dict(strong=r"banh chok|nom ?banh ?chok|num ?banh ?chok|nom ban chok|នំបញ្ចុក|khmer noodles", generic=r"$^",
                             queries=["num banh chok", "nom banh chok", "khmer noodles", "cambodian rice noodles fish curry"]),
    "kh_beef_salad": dict(strong=r"plea?h? sach ko|ភ្លាសាច់គោ", generic=r"beef salad",
                          queries=["plea sach ko", "cambodian beef salad", "khmer lime cured beef salad"]),
    "kh_prahok_ktiss": dict(strong=r"prahok k'?tis+|prahok ktis|ប្រហុកខ្ទិះ", generic=r"prahok",
                            queries=["prahok ktis", "prahok k'tis", "cambodian prahok coconut dip"]),
    "kh_samlor_korko": dict(strong=r"korko|ko ko soup|samlor kako|សម្លកកូរ", generic=r"$^",
                            queries=["samlor korko", "samlor kako", "cambodian korko soup"]),
    "kh_samlor_machu": dict(strong=r"machu|ma ?chou|សម្លម្ជូរ", generic=r"sour soup",
                            queries=["samlor machu", "khmer sour soup", "cambodian sour soup"]),
    "kh_sngao_ngam_ngov": dict(strong=r"ngam ngov|ngam nguv|sngor ngam|ស្ងោរញាំញូវ", generic=r"(pickled|salted) lime.{0,15}soup|lime soup",
                               queries=["ngam ngov", "khmer pickled lime chicken soup", "sngor ngam ngov"]),
    "kh_samlor_proher": dict(strong=r"proher|pror?hae?r|សម្លប្រហើរ", generic=r"$^",
                             queries=["samlor proher", "samlor pror", "khmer vegetable soup"]),
    "kh_kanh": dict(strong=r"\bkanh\b|កាញ់", generic=r"$^", queries=["kanh cambodia", "kanh khmer beef"]),
    "kh_steamed_fish_soy": dict(strong=r"ត្រីចំហុយ", generic=r"steamed (fish|snakehead|tilapia).{0,20}soy|soy.{0,20}steamed fish",
                                queries=["cambodian steamed fish soy sauce", "khmer steamed fish"]),
    # "amok" alone is also an English word (a film, a dance show, "running amok"): it needs the dish's own words or
    # Cambodia/Khmer next to it; files in the "Fish amok" Commons category are labelled by the category
    "kh_amok_trey": dict(strong=r"amok trey|fish amok|amok (curry|fish)|(khmer|cambodian) amok|amok.{0,15}(banana leaf|steamed)|អាម៉ុក",
                         generic=r"\bamok\b",
                         queries=["amok trey", "fish amok", "cambodian amok curry", "amok khmer steamed fish curry", "amok"]),
    "kh_kuy_teav": dict(strong=r"kuy ?t(e|i)a?e?v|kuyteav|kuy ?teow|គុយទាវ", generic=r"$^",
                        queries=["kuy teav", "kuyteav", "kuy teav phnom penh", "khmer noodle soup kuy teav", "kuy tiev"]),
    "kh_bai_sach_chrouk": dict(strong=r"sach ch?rou?k|សាច់ជ្រូក.{0,10}បាយ|បាយសាច់ជ្រូក", generic=r"(grilled|pork).{0,15}(broken )?rice",
                               queries=["bai sach chrouk", "cambodian pork and rice", "bai sach chrok breakfast"]),
    "kh_lort_cha": dict(strong=r"lort[ -]?ch?ha|lot ?cha|lor cha|លតឆា", generic=r"pin noodles|silver needle noodles",
                        queries=["lort cha", "lort cha cambodia", "cambodian fried short noodles"]),
    "kh_bok_lhong": dict(strong=r"bok l'?ho?ng|bok lahong|bok l?hong|បុកល្ហុង", generic=r"(green )?papaya salad",
                         queries=["bok lhong", "bok l'hong", "cambodian green papaya salad", "khmer papaya salad"]),
    "kh_num_pang": dict(strong=r"n[ou]m ?pang|nom pan\b|នំប៉័ង", generic=r"baguette|sandwich|banh mi",
                        queries=["num pang", "nom pang cambodia", "cambodian sandwich", "khmer baguette pate"]),
    "kh_sach_ko_ang": dict(strong=r"sach ko (ang|aing)|សាច់គោអាំង", generic=r"(grilled|bbq|barbecue).{0,10}(beef|skewers?)|beef skewers?",
                           queries=["sach ko ang", "cambodian grilled beef skewers", "khmer beef skewers"]),
    "kh_banh_chhev": dict(strong=r"banh chh?ae?v|banh chao|bahn chhev|បាញ់ឆែវ", generic=r"(crispy|cambodian|khmer) (crepe|pancake)",
                          queries=["banh chhev", "banh xeo cambodia", "cambodian crispy crepe", "khmer pancake banh chhev"]),
    "kh_borbor": dict(strong=r"\bbab?or\b|bor ?bor|bobor|បបរ", generic=r"(rice )?porridge|congee",
                      queries=["borbor cambodia", "bobor khmer rice porridge", "cambodian rice porridge", "khmer congee"]),
    "kh_chha_kdao": dict(strong=r"ch?ha k?dao|chhakdao|ឆាក្តៅ", generic=r"holy basil",
                         queries=["chha kdao", "cha kdao", "khmer holy basil stir fry", "cambodian basil beef stir fry"]),
}
ORIGINAL = list(D)                      # the 26 dishes the photo model knows
# recipes_khmer.csv rows that are the same dish as one above under another id
SAME_DISH = {"kh_amok", "kh_bok_lahong", "kh_num_pang_pate", "kh_sach_ko_ang_jakak"}


# Other names these dishes are known by (strong = only this dish has it; generic = needs Cambodia/Khmer next to it) and
# extra search words. Without these only the exact transliteration matches, and most dishes have several spellings.
EXTRA = {
    "kh_cha_kdam_kampot": dict(strong=r"kampot pepper crab|kdam ch?ha|pepper crab|crab.{0,15}(kampot|green pepper)", queries=["kampot pepper crab", "kdam chha kampot"]),
    "kh_nhoam_svay": dict(strong=r"nh?oam svay|nyoum svay|nhom svay|svay kchey|ញាំស្វាយ", generic=r"green mango salad|mango salad", queries=["green mango salad cambodia", "nhoam svay", "svay kchey salad"]),
    "kh_mee_kola": dict(strong=r"mi kola|kola noodle|មីកូឡា", queries=["mi kola battambang", "kola noodles"]),
    "kh_num_kom": dict(strong=r"n[ou]m kom|nom kom|នំគម", queries=["nom kom", "num kom khmer rice cake"]),
    "kh_sankhya_lapov": dict(strong=r"sangkhya|sankhya|sankaya|សង់ខ្យា", generic=r"pumpkin custard|custard pumpkin|kabocha custard", queries=["sangkhya lapov", "cambodian pumpkin custard", "sankaya fak thong"]),
    "kh_num_ansorm_chek": dict(strong=r"n[ou]m an?som|nom ansom|ansom chek|នំអន្សម", generic=r"banana.{0,20}(sticky rice|cake)", queries=["num ansom", "nom ansom chek", "cambodian banana sticky rice cake"]),
    "kh_num_plae_ai": dict(strong=r"n[ou]m plae ai|nom plae ai|plae ai|នំផ្លែអាយ", generic=r"(sticky rice|glutinous).{0,15}(ball|palm sugar)", queries=["num plae ai", "cambodian glutinous rice balls palm sugar"]),
    "kh_cha_houy_teuk": dict(strong=r"cha hou?y teuk|chaha|cha hoy|ចាហួយ", generic=r"khmer (jelly )?dessert|cambodian (jelly|dessert)", queries=["cha houy teuk", "cambodian jelly dessert", "khmer iced dessert"]),
    "kh_banh_ja_neuk": dict(strong=r"banh ja.?neuk|បាញ់ចានឿក", queries=["banh chaneuk", "cambodian sticky rice dumpling ginger syrup"]),
    "kh_khor_trey": dict(strong=r"kh?or trey|trey khor|ខត្រី", generic=r"caramel+i[sz]ed fish|braised fish", queries=["cambodian caramelised fish", "trei kor"]),
    "kh_cha_spey_kdov": dict(strong=r"spey kdov|ស្ពៃក្តោប", generic=r"stir.fried cabbage", queries=["cha spey kdov", "khmer stir fried cabbage"]),
    "kh_kuy_teav_kok": dict(strong=r"kuy ?teav kok|kuyteav kok|គុយទាវគោក", generic=r"dry (noodle|kuy)", queries=["kuy teav kok", "dry noodle phnom penh"]),
    "kh_cha_mi_hoon": dict(strong=r"cha mi ?hoon|mi sua|ឆាមីសួ", generic=r"stir.fried (glass|vermicelli|rice) noodles", queries=["cha mi hoon", "khmer stir fried vermicelli noodles"]),
    "kh_prahok_ang": dict(strong=r"prahok ang|ប្រហុកអាំង", generic=r"grilled prahok|prahok.{0,15}banana leaf", queries=["grilled prahok", "prahok ang banana leaf"]),
    "kh_teuk_kroeung": dict(strong=r"teuk kroeung|tuk kroeung|tuk kreung|teuk kreung|ទឹកគ្រឿង", generic=r"prahok dip|fish dip", queries=["tuk kreung", "prahok dip cambodia"]),
    "kh_saraman": dict(strong=r"saraman|sarmann|សារ៉ាម៉ាន់", generic=r"massaman|cambodian (beef )?curry", queries=["saraman curry", "cambodian massaman curry"]),
    "kh_nataing": dict(strong=r"natang|nataing|ណាតាំង", queries=["natang", "nataing dip"]),
    "kh_chek_ktis": dict(strong=r"chek ktis|ចេកខ្ទិះ", generic=r"banana.{0,15}coconut milk", queries=["chek ktis", "cambodian banana coconut milk dessert"]),
    "kh_fried_spider": dict(strong=r"a-?ping|aping|fried (tarantula|spider)|រពីង", generic=r"tarantula", queries=["fried tarantula cambodia", "a-ping skuon", "fried spider skuon"]),
    "kh_num_akor": dict(strong=r"n[ou]m a?h? ?kor|nom akor|នំអាកោរ", queries=["nom akor", "num akor"]),
    "kh_num_kreab": dict(strong=r"n[ou]m kreab|នំក្រៀប", queries=["num kreab", "cambodian rice cracker"]),
    "kh_bai_pong_moan": dict(strong=r"bai pong moan|បាយពងមាន់", generic=r"fried egg (and )?rice|egg rice", queries=["bai pong moan", "cambodian fried egg rice"]),
    "kh_borbor_tnaot": dict(strong=r"b[ao]b?or tnaot|bobor tnaot|បបរត្នោត", generic=r"palm (fruit|seed).{0,20}(pudding|porridge)", queries=["borbor tnaot", "cambodian palm fruit dessert"]),
    "kh_chha_trob": dict(strong=r"chha trob|cha trob|dot trob|ឆាត្រប់", generic=r"(char-?grilled|grilled) eggplant", queries=["chha trob", "grilled eggplant pork cambodia"]),
    "kh_tung_lamaow": dict(strong=r"lamaow|tung lamao|tung lemao", queries=["tung lamaow", "cham beef sausage"]),
    "kh_sngor_trey_bampe": dict(strong=r"bampe|ស្ងោរជ្រក់ត្រី", queries=["sngor trey bampe"]),
    "kh_samlor_machu_kroeung": dict(strong=r"machu kroeung|machou kroeung", queries=["samlor machu kroeung", "cambodian sour soup beef"]),
}


def add_new_dishes():
    """The other Khmer dishes of data/recipes_khmer.csv (no photos yet): the words that identify a dish are its own
    name (spaces/hyphens optional) and its Khmer name; no generic words, so a photo is kept only when it names the dish."""
    new = []
    for r in csv.DictReader(open(ROOT / "data" / "recipes_khmer.csv", encoding="utf-8")):
        i = r["dish_id"]
        if i in D or i in SAME_DISH:
            continue
        name = re.sub(r"\s*\(.*\)$", "", r["dish_name"]).strip()
        inside = re.findall(r"\(([^)]*)\)", r["dish_name"])
        kh = (r.get("dish_name_kh") or "").strip()
        strong = r"[ -]?".join(re.escape(w) for w in name.lower().split()) + (("|" + re.escape(kh)) if kh else "")
        queries = [q for q in [name, f"{name} cambodia", (inside[0] + " cambodia") if inside else "", kh] if q]
        x = EXTRA.get(i, {})
        D[i] = dict(strong=strong + (("|" + x["strong"]) if x.get("strong") else ""), generic=x.get("generic", r"$^"),
                    queries=queries + x.get("queries", []))
        new.append(i)
    return new


# Commons categories to crawl: the category NAME is matched against each dish's `strong` words
COMMONS_ROOTS = ["Category:Cuisine of Cambodia", "Category:Cambodian cuisine", "Category:Food of Cambodia",
                 "Category:Cambodian noodle dishes", "Category:Cambodian soups", "Category:Cambodian salads",
                 "Category:Cambodian curries", "Category:Street food of Cambodia", "Category:Cambodian dishes"]

BUDGET_FILE = KH / "openverse_budget.json"      # {"date": ..., "count": n}: the anonymous limit is 200 requests a day


def openverse_used():
    try:
        b = json.loads(BUDGET_FILE.read_text())
        return b["count"] if b["date"] == time.strftime("%Y-%m-%d") else 0
    except (OSError, ValueError, KeyError):
        return 0


def openverse_count():
    BUDGET_FILE.write_text(json.dumps({"date": time.strftime("%Y-%m-%d"), "count": openverse_used() + 1}))


BROWSER = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
           "Accept-Language": "en-US,en;q=0.9"}
KH_NAME = {r["dish_id"]: r["name_kh"] for r in csv.DictReader(open(ROOT / "data" / "dish_knowledge.csv", encoding="utf-8")) if r["name_kh"]}
http = requests.Session()
http.headers["User-Agent"] = UA


def get(url, params=None, tries=6, gap=0.0, **kw):
    """GET with the polite parts: wait `gap` first, obey Retry-After on 429/503, back off on errors."""
    for i in range(tries):
        time.sleep(gap)
        try:
            r = http.get(url, params=params, timeout=kw.pop("timeout", 30), **kw)
        except requests.RequestException as e:
            log.warning("request failed (%s), retry %d", type(e).__name__, i + 1)
            time.sleep(2 ** i)
            continue
        if r.status_code in (429, 503):
            wait = float(r.headers.get("retry-after", 5)) * (1.5 + i)
            if wait > MAX_WAIT:
                log.info("host asks for a %.0fs pause: skipping this file (run again later)", wait)
                return None
            log.info("rate limited (%d), waiting %.0fs", r.status_code, wait)
            time.sleep(wait)
            continue
        return r
    return None


def dhash(img: Image.Image) -> int:
    px = list(img.convert("L").resize((9, 8), Image.LANCZOS).getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    return bits


class Seen:
    """The difference hashes of every photo we already have (combined, harvested, rejected) and of this run's."""

    def __init__(self):
        self.hashes = []
        files = [p for d in ("combined/images", "harvested", "rejected") for p in (KH / d).rglob("*")
                 if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
        for p in files:
            try:
                with Image.open(p) as im:
                    self.hashes.append(dhash(im))
            except Exception:
                pass
        log.info("%d existing photos hashed", len(self.hashes))

    def dup(self, h):
        return any(bin(h ^ o).count("1") <= 4 for o in self.hashes)

    def add(self, h):
        self.hashes.append(h)


def relevant(dish, text, in_category=False):
    d = D[dish]
    if in_category or re.search(d["strong"], text, re.I):
        return True
    return bool(re.search(d["generic"], text, re.I)) and bool(CONTEXT.search(text))


def strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(s) if s is not None else "")).strip()


# ---------------------------------------------------------------- Wikimedia Commons
COMMONS = "https://commons.wikimedia.org/w/api.php"
IMG_PROPS = dict(prop="imageinfo", iiprop="url|mime|size|extmetadata", iiurlwidth=960)


def commons_items(params, max_pages=4):
    """Pages (files) of a generator query, following `continue` for at most max_pages requests (a text search for
    "amok" matches thousands of unrelated files; the relevant ones come first)."""
    cont = {}
    for _ in range(max_pages):
        r = get(COMMONS, dict(action="query", format="json", **IMG_PROPS, **params, **cont), gap=1.2)
        if r is None or r.status_code != 200:
            return
        try:
            j = r.json()
        except ValueError:
            return
        for p in (j.get("query", {}).get("pages") or {}).values():
            yield p
        if "continue" not in j:
            return
        cont = j["continue"]


def commons_candidates(dish):
    """Search by text: the dish queries (files only)."""
    for q in D[dish]["queries"]:
        for p in commons_items(dict(generator="search", gsrsearch=q, gsrnamespace=6, gsrlimit=50)):
            yield p, False


def commons_category_tree():
    """The names of the Cambodian-food categories (two levels of sub-categories). Cached: the crawl takes minutes."""
    if CATEGORY_CACHE.exists() and time.time() - CATEGORY_CACHE.stat().st_mtime < 7 * 86400:
        return json.loads(CATEGORY_CACHE.read_text(encoding="utf-8"))
    seen, frontier, cats = set(), list(COMMONS_ROOTS), {}
    for depth in range(3):
        nxt = []
        for c in frontier:
            if c in seen:
                continue
            seen.add(c)
            cont = {}
            while True:
                r = get(COMMONS, dict(action="query", format="json", list="categorymembers", cmtitle=c, cmtype="subcat",
                                      cmlimit=500, **cont), gap=1.2)
                if r is None or r.status_code != 200:
                    break
                j = r.json()
                nxt += [m["title"] for m in j.get("query", {}).get("categorymembers", [])]
                if "continue" not in j:
                    break
                cont = j["continue"]
            cats[c] = True
        frontier = nxt
    names = sorted(seen | set(frontier))
    log.info("Commons: %d Cambodian-food categories found", len(names))
    CATEGORY_CACHE.write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
    return names


def commons_category_candidates(dish, categories):
    names = [c for c in categories if re.search(D[dish]["strong"], c, re.I)]
    for c in names:
        log.info("  category %s", c)
        for p in commons_items(dict(generator="categorymembers", gcmtitle=c, gcmtype="file", gcmlimit=50), max_pages=10):
            yield p, True


def commons_record(p):
    ii = (p.get("imageinfo") or [None])[0]
    if not ii or ii.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
        return None
    meta = {k: strip_html(v.get("value")) for k, v in (ii.get("extmetadata") or {}).items()}
    text = " ".join([p.get("title", ""), meta.get("ImageDescription", ""), meta.get("Categories", "").replace("|", " "),
                     meta.get("ObjectName", "")])
    return dict(id=f"cm_{p['pageid']}", url=ii.get("thumburl") or ii["url"], text=text, source="commons",
                title=p.get("title", "").removeprefix("File:"), creator=meta.get("Artist", "")[:120],
                license=meta.get("LicenseShortName", ""), license_url=meta.get("LicenseUrl", ""),
                page=ii.get("descriptionurl", ""), width=ii.get("thumbwidth") or ii.get("width"))


# ---------------------------------------------------------------- Openverse
OPENVERSE = "https://api.openverse.org/v1/images/"

def openverse_candidates(dish, pages, budget):
    for q in D[dish]["queries"][:budget]:
        for page in range(1, pages + 1):
            if openverse_used() >= 195:
                log.warning("Openverse: daily anonymous limit (200) reached")
                return
            openverse_count()
            r = get(OPENVERSE, dict(q=q, page=page, page_size=20), gap=3.2)
            if r is None or r.status_code != 200:
                break
            res = r.json().get("results", [])
            for x in res:
                yield x, q
            if len(res) < 20:
                break


def openverse_record(x):
    text = " ".join([x.get("title") or "", " ".join(t.get("name", "") for t in (x.get("tags") or []))])
    return dict(id=f"ov_{x['id'][:8]}", url=x["url"], text=text, source="openverse", title=(x.get("title") or "")[:150],
                creator=(x.get("creator") or "")[:120], license=f"{x.get('license', '')} {x.get('license_version', '')}".strip(),
                license_url=x.get("license_url") or "", page=x.get("foreign_landing_url") or "",
                width=x.get("width"))


# ---------------------------------------------------------------- Bing images (no licence information)
BING = "https://www.bing.com/images/search"


def bing_candidates(dish, pages):
    """Result entries of Bing image search for the dish's queries, its Khmer name and "<name> khmer food"."""
    first_q = D[dish]["queries"][0]
    queries = list(dict.fromkeys(D[dish]["queries"] + [KH_NAME.get(dish, ""), f"{first_q} khmer food"]))
    for q in [q for q in queries if q]:
        for page in range(pages):
            r = get(BING, dict(q=q, first=1 + 35 * page), gap=2.0, tries=3, headers=BROWSER)
            if r is None or r.status_code != 200:
                break
            items = []
            for m in re.findall(r'class="iusc"[^>]*\sm="([^"]+)"', r.text):
                try:
                    items.append(json.loads(html.unescape(m)))
                except ValueError:
                    pass
            yield from items
            if len(items) < 20:
                break


def bing_record(x):
    if not x.get("murl"):
        return None
    return dict(id="bg_" + (x.get("md5") or hashlib.md5(x["murl"].encode()).hexdigest())[:10], url=x["murl"],
                text=" ".join([x.get("t") or "", x.get("desc") or "", x.get("purl") or ""]), source="bing",
                title=(x.get("t") or "")[:150], creator="", license="unknown (web image search)", license_url="",
                page=x.get("purl") or "", width=None)


# ---------------------------------------------------------------- download and save
def fetch(rec):
    """-> (PIL image or None) for a record: downloads it, checks it is a usable photo."""
    r = get(rec["url"], gap=1.0 if rec["source"] == "commons" else 0.2, tries=3 if rec["source"] != "bing" else 2, timeout=25 if rec["source"] != "bing" else 12,
            headers=BROWSER if rec["source"] == "bing" else None)
    if r is None or r.status_code != 200 or not (5000 < len(r.content) < 25_000_000):
        return None
    try:
        im = Image.open(io.BytesIO(r.content))
        im.load()
        im = im.convert("RGB")
    except Exception:
        return None
    w, h = im.size
    if min(w, h) < MIN_SIDE or not (0.45 <= w / h <= 2.4):
        return None
    if max(w, h) > MAX_SIDE:
        im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    return im


def harvest_dish(dish, cands, seen, cap, rows, existing_ids):
    """cands: iterable of (record, in_category). Saves new relevant photos; returns how many."""
    folder = OUT / dish
    folder.mkdir(parents=True, exist_ok=True)
    have = len(list(folder.glob("*.jpg")))
    todo, ids = [], set()
    for rec, in_cat in cands:
        if rec is None or rec["id"] in existing_ids or rec["id"] in ids or not relevant(dish, rec["text"], in_cat):
            continue
        ids.add(rec["id"])
        todo.append(rec)
    saved = 0
    with ThreadPoolExecutor(1 if todo and todo[0]["source"] == "commons" else 4) as pool:
        for rec, im in zip(todo, pool.map(fetch, todo)):
            if have + saved >= cap:
                break
            if im is None:
                continue
            h = dhash(im)
            if seen.dup(h):
                continue
            seen.add(h)
            path = folder / f"{rec['id']}.jpg"
            im.save(path, "JPEG", quality=90)
            existing_ids.add(rec["id"])
            write_sources([{"dish_id": dish, "file": f"{dish}/{path.name}", **{k: rec[k] for k in
                           ("source", "title", "creator", "license", "license_url", "page")}}])
            saved += 1
    return saved


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dishes", default="", help="comma-separated dish ids (default: the 26 the photo model knows)")
    ap.add_argument("--new", action="store_true", help="the other Khmer dishes of data/recipes_khmer.csv instead")
    ap.add_argument("--sources", default="commons,openverse")
    ap.add_argument("--cap", type=int, default=400, help="stop a dish at this many harvested photos")
    ap.add_argument("--openverse-pages", type=int, default=2)
    ap.add_argument("--bing-pages", type=int, default=3, help="pages of 35 results per query")
    ap.add_argument("--openverse-queries", type=int, default=3)
    a = ap.parse_args()
    new_ids = add_new_dishes()
    dishes = [d for d in (a.dishes.split(",") if a.dishes else new_ids if a.new else ORIGINAL) if d]
    bad = [d for d in dishes if d not in D]
    if bad:
        sys.exit(f"unknown dish ids: {bad}")
    sources = set(a.sources.split(","))

    seen = Seen()
    rows = []
    existing_ids = {p.stem for p in OUT.rglob("*.jpg")}
    categories = commons_category_tree() if "commons" in sources else []
    totals = {}
    # dishes with the fewest photos first: Openverse's daily budget goes to the ones that need it most
    dishes.sort(key=lambda d: len(list((OUT / d).glob("*.jpg"))) + len(list((KH / "combined/images" / d).glob("*.jpg"))))
    for i, dish in enumerate(dishes, 1):
        before = len(list((OUT / dish).glob("*.jpg"))) if (OUT / dish).exists() else 0
        log.info("[%d/%d] %s: %d harvested photos so far", i, len(dishes), dish, before)
        n = 0
        if "commons" in sources:
            cands = ((commons_record(p), c) for p, c in commons_category_candidates(dish, categories))
            n += harvest_dish(dish, cands, seen, a.cap, rows, existing_ids)
            cands = ((commons_record(p), c) for p, c in commons_candidates(dish))
            n += harvest_dish(dish, cands, seen, a.cap, rows, existing_ids)
        if "openverse" in sources:
            cands = ((openverse_record(x), False) for x, _ in openverse_candidates(dish, a.openverse_pages, a.openverse_queries))
            n += harvest_dish(dish, cands, seen, a.cap, rows, existing_ids)
        if "bing" in sources:
            cands = ((bing_record(x), False) for x in bing_candidates(dish, a.bing_pages))
            n += harvest_dish(dish, cands, seen, a.cap, rows, existing_ids)
        totals[dish] = n
        log.info("    + %d new photos for %s", n, dish)
    log.info("DONE: %d new photos. Sources: %s", sum(totals.values()), SOURCES_CSV)
    for d, n in sorted(totals.items(), key=lambda kv: -kv[1]):
        print(f"{n:4} {d}")


def write_sources(rows):
    new = not SOURCES_CSV.exists()
    with SOURCES_CSV.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["dish_id", "file", "source", "title", "creator", "license", "license_url", "page"])
        if new:
            w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()

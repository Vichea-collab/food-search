"""
Build data/dish_knowledge.csv: what each dish the app knows IS (for "what is kuy teav?", or just "kuy teav"), in English
and Khmer, with its source.

  English  the first sentences of the dish's Wikipedia article (REST "page summary" API; text CC BY-SA 4.0, so the app
           shows the source link). A dish without a matching article keeps our own one-line description
           (data/recipes_khmer.csv, source "Klean Nham").
  Khmer    translated from the English by the AI model (Gemini) and marked as such in `about_kh_by`, so a person can
           check and correct it. Rows already translated are kept when the script runs again (--retranslate redoes them).

A page counts as the dish's article only if it is about food (its Wikipedia description or text has a food word) and
its title shares a word with the dish's name or a known alias, so "Prahok ktiss" never gets the article about prahok
itself. TITLES below fixes the names Wikipedia spells differently. Every match is printed: look through them.

Usage:
    venv/bin/python scrapers/dish_knowledge.py              # fetch, translate what is new, write the CSV
    venv/bin/python scrapers/dish_knowledge.py --no-translate
    venv/bin/python scrapers/dish_knowledge.py --retranslate
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
OUT = ROOT / "data" / "dish_knowledge.csv"
UA = {"User-Agent": "KleanNham/1.0 (student course project; food search for Cambodia)"}
MAX_SENTENCES, MAX_CHARS = 3, 480

# dish id -> Wikipedia title, where the dish's own name is not the article's (or is ambiguous). None = no article
TITLES = {
    # Khmer dishes. A general article (Cambodian cuisine, Stew, Vegetable soup) or another country's dish (lok lak ->
    # the Vietnamese "Shaking beef") would describe the wrong thing: those keep our own text (None)
    "kh_amok": "Fish amok", "kh_kuy_teav": "Kuyteav", "kh_samlor_korko": "Samlar kako",
    "kh_num_banh_chok": "Num banhchok", "kh_bai_sach_chrouk": "Bay sach chruk", "kh_num_pang_pate": "Num pang",
    "kh_lort_cha": "Lort cha", "kh_num_plae_ai": "Num plae ai", "kh_samlor_machu_ktis": "Samlor machu ktis",
    "kh_bok_lahong": "Green papaya salad",
    "kh_lok_lak": None, "kh_kari": None, "kh_beef_stew": None, "kh_samlor_proher": None, "kh_samlor_machu": None,
    "kh_prahok_ktiss": None, "kh_prahok_ang": None, "kh_kanh": None, "kh_khor": None, "kh_kuy_teav_kok": None,
    "kh_num_banh_chok_kampot": None, "kh_num_kom": None, "kh_num_ansorm_chek": None, "kh_cha_houy_teuk": None,
    "kh_sankhya_lapov": None, "kh_banh_ja_neuk": None,
    # Food-101 dishes whose article has another name
    "baby_back_ribs": "Pork ribs", "beef_carpaccio": "Carpaccio", "beef_tartare": "Steak tartare",
    "beignets": "Beignet", "breakfast_burrito": "Breakfast burrito", "chicken_quesadilla": "Quesadilla",
    "chicken_wings": "Buffalo wing", "chocolate_mousse": "Mousse", "churros": "Churro", "crab_cakes": "Crab cake",
    "cup_cakes": "Cupcake", "deviled_eggs": "Deviled egg", "donuts": "Doughnut",
    "dumplings": "Dumpling", "escargots": "Snails as food", "fried_calamari": "Squid as food",
    "grilled_cheese_sandwich": "Grilled cheese", "grilled_salmon": "Salmon as food", "gyoza": "Jiaozi",
    "lobster_bisque": "Bisque (food)", "lobster_roll_sandwich": "Lobster roll", "macarons": "Macaron",
    "mussels": "Mussel", "onion_rings": "Onion ring", "oysters": "Oyster", "pancakes": "Pancake", "pho": "Pho",
    "prime_rib": "Standing rib roast", "pulled_pork_sandwich": "Barbecue sandwich", "scallops": "Scallop",
    "spaghetti_bolognese": "Bolognese sauce", "spaghetti_carbonara": "Carbonara", "spring_rolls": "Spring roll",
    "strawberry_shortcake": "Shortcake", "tacos": "Taco", "waffles": "Waffle",
    "beet_salad": None, "cheese_plate": None, "seaweed_salad": None, "tuna_tartare": None, "croque_madame": None,
}
# a short description of our own for dishes without a matching article (and no Khmer recipe text)
OWN_TEXT = {
    "beet_salad": "A salad of cooked or roasted beetroot, often with leafy greens, cheese such as goat cheese, and nuts.",
    "breakfast_burrito": "A Mexican-American burrito for breakfast: a flour tortilla rolled around scrambled eggs, "
                         "often with potatoes, cheese and bacon or sausage.",
    "cheese_plate": "A selection of different cheeses served together, usually with bread or crackers, fruit and nuts.",
    "croque_madame": "A French hot ham and cheese sandwich (a croque monsieur) topped with a fried or poached egg.",
    "oysters": "Oysters are shellfish eaten raw on the half shell, often with lemon, or grilled, steamed or fried.",
    "seaweed_salad": "A Japanese-style salad of thin strips of seaweed, usually wakame, dressed with sesame oil, "
                     "vinegar and sesame seeds.",
    "tuna_tartare": "Raw tuna cut into small cubes and seasoned, often with soy sauce, sesame, avocado or citrus.",
    "kh_kanh": "Kanh is a Cambodian minced beef salad.",
}
FOOD_WORDS = re.compile(r"\b(dish|food|cuisine|soup|stew|salad|noodles?|rice|cake|pastry|dessert|sauce|bread|"
                        r"sandwich|curry|snack|meat|beef|pork|chicken|fish|seafood|dumplings?|pudding|sweet|fried|"
                        r"grilled|baked|cheese|egg|eaten|cooked|served|recipe|delicacy|mollusc|squid|shellfish|"
                        r"confection|custard|drink|appetizer|condiment|dip)\b", re.I)
STOP = {"the", "and", "with", "of", "in", "a", "style", "food", "as", "dish", "soup", "salad", "sauce", "khmer",
        "cambodian", "fried", "grilled", "sweet", "sour", "stir", "fresh"}


def words(text) -> set:
    return {w for w in re.findall(r"[a-zà-ỹ]+", str(text).lower()) if len(w) > 2 and w not in STOP}


def first_sentences(text, n=MAX_SENTENCES, limit=MAX_CHARS) -> str:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", " ".join(str(text).split()))
    out = ""
    for p in parts[:n]:
        if out and len(out) + 1 + len(p) > limit:
            break
        out = f"{out} {p}".strip()
    return out


def summary(title):
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(title.replace(" ", "_"), safe="")
    for attempt in range(6):                     # Wikipedia limits the request rate: wait longer each time
        r = requests.get(url, headers=UA, timeout=20)
        if r.status_code in (429, 503):
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 404:
            return None
        if not r.ok:
            raise RuntimeError(f"Wikipedia answered {r.status_code} for {title}")
        return r.json()
    raise RuntimeError(f"Wikipedia kept refusing ({title}); run the script again later")


def match(dish_id, name, aliases):
    """(title, extract, url) of the dish's article, or None."""
    if dish_id in TITLES and TITLES[dish_id] is None:
        return None
    candidates = [TITLES[dish_id]] if dish_id in TITLES else [name.split(" (")[0], *aliases]
    names = words(name) | set().union(*(words(a) for a in aliases)) if aliases else words(name)
    for title in dict.fromkeys(c for c in candidates if c):
        s = summary(title)
        time.sleep(1.0)
        if not s or s.get("type") != "standard" or not s.get("extract"):
            continue
        about_food = FOOD_WORDS.search(f"{s.get('description', '')} {s['extract'][:300]}")
        same_dish = dish_id in TITLES or words(s["title"]) & names
        if about_food and same_dish:
            return s["title"], first_sentences(s["extract"]), s["content_urls"]["desktop"]["page"]
    return None


TRANSLATE_PROMPT = (
    "Translate this English description of a dish into natural, simple Khmer for a food app in Cambodia. Translate "
    "every sentence completely; keep the meaning exactly and add nothing. Use Khmer script only: no Thai letters and "
    "no English words, except a foreign dish or ingredient name with no Khmer spelling. Write well-known dish names the "
    "way Cambodians write them (e.g. គុយទាវ, អាម៉ុក, ភីហ្សា, ស៊ូស៊ី). Reply with the Khmer text only.\n\n")
# the lite model: Gemini 3.6 Flash had no free quota left, and the local Qwen mixes in Thai letters (9 Nov)
TRANSLATE_MODEL = "gemini:gemini-3.5-flash-lite"
KHMER_CHARS = re.compile(r"[\u1780-\u17ff]")
# foreign food names that may stay in Latin letters inside the Khmer text
FOREIGN_FOOD = {"carpaccio", "tartare", "filo", "phyllo", "romaine", "hollandaise", "mignon", "gras", "feta", "paneer",
                "grits", "burrito", "tortilla", "tortillas", "mayonnaise", "mozzarella", "ricotta", "mascarpone",
                "parmesan", "pesto", "dashi", "miso", "shari", "sumeshi", "wasabi", "kimchi", "gochujang", "tahini",
                "bisque", "chowder", "ragù", "pecorino", "guanciale", "pancetta", "dulce", "leche", "ganache"}


def kh_problem(en, kh):
    """Why a Khmer translation cannot be used as it is, or None."""
    if not kh:
        return "missing"
    if re.search(r"[\u0e00-\u0eff]", kh):
        return "Thai or Lao letters"
    left = [w for w in re.findall(r"(?<![A-Za-z])[a-z]{4,}(?![A-Za-z])", kh) if w not in FOREIGN_FOOD]
    if left:
        return f"English words left ({', '.join(left[:3])})"
    if len(KHMER_CHARS.findall(kh)) < 0.55 * len(re.findall(r"[A-Za-z]", en)):
        return "too short (sentences left out?)"
    return None


def translate_one(en, tries=3):
    """(Khmer, model label) or None: the first translation that passes kh_problem."""
    from food_search.llm import NoModelAnswered, complete
    for _ in range(tries):
        try:
            text, model = complete(TRANSLATE_PROMPT + en, TRANSLATE_MODEL, max_models=1, timeout_s=60)
        except NoModelAnswered:
            time.sleep(20)                              # busy or the per-minute limit: wait, then try again
            continue
        kh = " ".join(text.strip().strip('"').split())
        time.sleep(4)                                   # stay under the free per-minute limit (the live app uses it too)
        if not kh_problem(en, kh):
            return kh, model["label"] or model["id"]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-translate", action="store_true")
    ap.add_argument("--retranslate", action="store_true")
    args = ap.parse_args()
    from food_search import dishes
    dishes.init()
    old = (pd.read_csv(OUT, dtype=str).fillna("").set_index("dish_id").to_dict("index") if OUT.exists() else {})
    own = pd.read_csv(ROOT / "data" / "recipes_khmer.csv", dtype=str).fillna("").set_index("dish_id")["description"]
    rows = []
    for dish_id, name in dishes.DISHES.items():
        info = dishes.DISH_INFO.get(dish_id, {})
        aliases = [a for a in info.get("aliases", []) if re.fullmatch(r"[A-Za-z' -]+", a)] if isinstance(info, dict) else []
        found = match(dish_id, name, aliases)
        if found:
            title, text, url = found
            row = {"about_en": text, "source": "Wikipedia", "source_title": title, "source_url": url,
                   "license": "CC BY-SA 4.0"}
        elif own.get(dish_id) or OWN_TEXT.get(dish_id):
            row = {"about_en": own.get(dish_id) or OWN_TEXT[dish_id], "source": "Klean Nham", "source_title": "", "source_url": "", "license": ""}
        else:
            print(f"  ✗ {dish_id:28} no article and no description of our own")
            continue
        print(f"  {'✓' if found else '·'} {dish_id:28} {row['source_title'] or '(our own text)':28} {row['about_en'][:70]}")
        prev = old.get(dish_id, {})
        keep = (prev.get("about_en") == row["about_en"] and not kh_problem(row["about_en"], prev.get("about_kh", ""))
                and not args.retranslate)
        rows.append({"dish_id": dish_id, "name_en": name, "name_kh": info.get("name_kh", "") if isinstance(info, dict) else "",
                     **row, "about_kh": prev.get("about_kh", "") if keep else "",
                     "about_kh_by": prev.get("about_kh_by", "") if keep else ""})
    todo = [r for r in rows if not r["about_kh"]]
    if todo and not args.no_translate:
        print(f"translating {len(todo)} descriptions into Khmer, one at a time…")
        for r in todo:
            done = translate_one(r["about_en"])
            if done:
                r["about_kh"], r["about_kh_by"] = done[0], f"machine translation ({done[1]})"
            else:
                print(f"  ✗ {r['dish_id']:28} no usable Khmer translation yet (run the script again later)")
    for r in rows:                                       # still not usable: kept out, the app answers in English
        why = kh_problem(r["about_en"], r["about_kh"])
        if why and r["about_kh"]:
            print(f"  ! {r['dish_id']:28} Khmer not used: {why}")
            r["about_kh"], r["about_kh_by"] = "", ""
    cols = ["dish_id", "name_en", "name_kh", "about_en", "about_kh", "about_kh_by", "source", "source_title",
            "source_url", "license"]
    pd.DataFrame(rows, columns=cols).to_csv(OUT, index=False)
    wiki = sum(r["source"] == "Wikipedia" for r in rows)
    kh = sum(bool(r["about_kh"]) for r in rows)
    print(f"{len(rows)} of {len(dishes.DISHES)} dishes -> {OUT.relative_to(ROOT)} "
          f"(Wikipedia {wiki}, our own text {len(rows) - wiki}; Khmer {kh})")


if __name__ == "__main__":
    main()

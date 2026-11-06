"""
Nationwide Cambodia Dataset Normalization & Deduplication Pipeline (facts only)
Scopes across all of Cambodia (Phnom Penh, Siem Reap, Battambang, Sihanoukville, Kampot, etc.).

FACTS ONLY: the chatbot answers from this file and promises never to invent anything, so a value a source does not
really provide stays EMPTY. No default prices, ratings, opening hours, coordinates, stock photos or "popular menu
items" are filled in. Dish types inferred from a place's own name or tags are kept (they are evidence-based).
"""

import re
import csv
import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

# Standard searchable columns + page_url + menu + image_url
ALL_COLUMNS = [
    "id", "name", "dish_en", "dish_kh", "description", "tags", "price_usd",
    "area", "lat", "lng", "rating", "open_hour", "close_hour", "source",
    "source_url", "date", "image_url", "phone_public"
]
DATA_COLUMNS = ALL_COLUMNS + ["page_url", "menu", "image_path"]

# Fields that a scraper filled with a default instead of reading it from the source. They are cleared here, so files
# scraped before the scrapers were fixed are cleaned too. (foodpanda: price inferred from the dish type, rating 4.5 and
# hours 7-22 for everyone; wownow: city-centre coordinates, rating 4.5, hours 7-22; grabfood / foodchow: city-centre
# coordinates; yellowpages: a $5 "baseline" price.)
GUESSED_FIELDS = {
    "foodpanda": {"price_usd", "rating", "open_hour", "close_hour"},
    "wownow-telegram": {"lat", "lng", "rating", "open_hour", "close_hour", "dish_en", "dish_kh"},
    "grabfood": {"lat", "lng", "open_hour", "close_hour"},
    "foodchow": {"lat", "lng"},
    "yellowpages-cambodia": {"price_usd", "rating"},
    "overture": {"price_usd", "rating", "open_hour", "close_hour"},    # the scraper wrote 4.5, a price and hours by category
}
# Defaults a scraper used only when the page had no value: equal to the default = unknown (yellowpages: 10:00-22:00).
DEFAULT_HOURS = {"yellowpages-cambodia": ("10.0", "22.0")}
# Rows that are not places to eat: GrabFood category pages
NOT_PLACES = {"grabfood", "culinary-lexicon", "khmer-culinary-lexicon", "wikidata"}     # + lists of dishes, not places
GENERIC_NAMES = {"wownow merchant", "special", "food venue", "restaurant", "unknown", ""}
STOCK_PHOTO_HOSTS = ("images.unsplash.com",)
# Overture places of an unknown cuisine got a made-up dish and tags, and every Overture place got "delivery"
GUESSED_DISH = "Khmer & Asian Made-to-Order Dishes"
GUESSED_TAGS = {"khmer", "rice", "dinner"}
GUESSED_DISH_SENTENCE_RE = re.compile(
    r"Serving Khmer & Asian Made-to-Order Dishes \([^)]*\) in [^.]*\.\s*(?:មានបម្រើ[^។]*។)?", re.I)
# Sentences that scrapers wrote from templates (not from the source) and must not reach the chatbot as facts.
TEMPLATE_SENTENCE_RE = re.compile(
    r"(?:Popular menu items:[^.។]*[.។]?\s*(?:មុខម្ហូបពិសេសៗ៖[^។]*។)?"
    r"|Price:[^.។]*(?:\.\d+)?[^.។]*[.។]?\s*(?:តម្លៃ[^។]*។)?"
    r"|Dine-in and takeaway available\.\s*(?:អាចញ៉ាំនៅកន្លែង ឬទិញខ្ចប់បាន។)?"
    r"|Foodpanda restaurant partner in [^.]*\.)",
    re.I)


# "Open: 07:00 - 22:00 (ម៉ោងបើកលក់៖ 07:00 ដល់ 22:00)។" written into the text by a scraper (also cut-off copies of it)
OPEN_SENTENCE_RE = re.compile(r"Open:\s*[\d:]+\s*-?\s*[\d:]*\s*(?:\(ម៉ោងបើកលក់៖[^)]*\)?)?\s*។?")


def unique_sentences(text: str) -> str:
    """Drops sentences that are repeated word for word (a description built twice)."""
    seen, out = set(), []
    for part in re.split(r"(?<=[.។])\s+", text):
        key = part.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(part.strip())
    return " ".join(out)


def keep_facts_only(df: pd.DataFrame) -> pd.DataFrame:
    """Drops rows that are not places, and clears every value a source did not really provide."""
    before = len(df)
    src = df["source"].str.lower()
    df = df[~src.isin(NOT_PLACES)]
    df = df[~df["name"].str.strip().str.lower().isin(GENERIC_NAMES)]
    df = df[df["name"].str.contains(r"[A-Za-z0-9\u1780-\u17FF]", regex=True)].copy()      # e.g. a name that is only "🎉"
    print(f"Facts only: dropped {before - len(df)} rows that are not places (dishes, category pages, promo posts)")
    for source, fields in GUESSED_FIELDS.items():
        rows = df["source"].str.lower().eq(source)
        for col in fields:
            df.loc[rows, col] = ""
        if rows.any():
            print(f"Facts only: cleared guessed {sorted(fields)} for {rows.sum()} {source} rows")
    for source, (open_h, close_h) in DEFAULT_HOURS.items():
        rows = df["source"].str.lower().eq(source) & df["open_hour"].eq(open_h) & df["close_hour"].eq(close_h)
        df.loc[rows, ["open_hour", "close_hour"]] = ""
        if rows.any():
            print(f"Facts only: cleared {rows.sum()} default opening hours ({open_h}-{close_h}) of {source}")
    if "menu" in df.columns:                                   # no source gives a menu: they were typed into a script
        df["menu"] = ""
    unknown_dish = df["dish_en"].eq(GUESSED_DISH)
    df.loc[unknown_dish, ["dish_en", "dish_kh"]] = ""
    df.loc[unknown_dish, "tags"] = df.loc[unknown_dish, "tags"].map(
        lambda t: ";".join(x for x in t.split(";") if x and x not in GUESSED_TAGS))
    only_overture = df["source"].str.lower().eq("overture")
    df.loc[only_overture, "tags"] = df.loc[only_overture, "tags"].map(
        lambda t: ";".join(x for x in t.split(";") if x and x != "delivery"))       # nothing says it delivers
    df["description"] = df["description"].str.replace(GUESSED_DISH_SENTENCE_RE, " ", regex=True)
    print(f"Facts only: cleared {int(unknown_dish.sum())} guessed cuisines, all menus, and the 'delivery' tag of "
          f"{int(only_overture.sum())} Overture places")
    stock_col = df["image_url"] if "image_url" in df.columns else df["image_path"]
    stock = stock_col.str.contains("|".join(map(re.escape, STOCK_PHOTO_HOSTS)), regex=True)
    if "image_url" in df.columns:
        df.loc[stock, "image_url"] = ""
    if "image_path" in df.columns:
        df.loc[stock, "image_path"] = ""
    df["description"] = df["description"].str.replace(TEMPLATE_SENTENCE_RE, " ", regex=True).str.replace(r"\s+", " ", regex=True).str.strip()
    guessed_hours = df["source"].str.lower().isin([s for s, f in GUESSED_FIELDS.items() if "open_hour" in f])
    df.loc[guessed_hours, "description"] = df.loc[guessed_hours, "description"].str.replace(OPEN_SENTENCE_RE, " ", regex=True)
    df["description"] = df["description"].str.replace(r"\s+", " ", regex=True).str.strip().map(unique_sentences)
    return df

# All 25 Provinces & Municipalities of Cambodia
CAMBODIA_PROVINCES = [
    "Phnom Penh",
    "Siem Reap",
    "Battambang",
    "Preah Sihanouk",
    "Kampot",
    "Kep",
    "Kandal",
    "Kampong Cham",
    "Banteay Meanchey",
    "Svay Rieng",
    "Koh Kong",
    "Pursat",
    "Kampong Chhnang",
    "Kampong Speu",
    "Kampong Thom",
    "Kratie",
    "Stung Treng",
    "Mondulkiri",
    "Ratanakiri",
    "Preah Vihear",
    "Takeo",
    "Prey Veng",
    "Oddar Meanchey",
    "Pailin",
    "Tboung Khmum",
]

# Area normalization map (Phnom Penh Khans + Provinces)
AREA_NORMALIZATION = {
    # Phnom Penh Khans
    "bkk": "Boeung Keng Kang", "bkk1": "Boeung Keng Kang", "bkk2": "Boeung Keng Kang", "bkk3": "Boeung Keng Kang",
    "boeung keng kang": "Boeung Keng Kang", "boeng keng kang": "Boeung Keng Kang",
    "chamkar mon": "Chamkar Mon", "chamkarmon": "Chamkar Mon", "chamkar morn": "Chamkar Mon",
    "daun penh": "Daun Penh", "doun penh": "Daun Penh", "don penh": "Daun Penh",
    "toul kork": "Toul Kork", "tuol kork": "Toul Kork", "tuol kouk": "Toul Kork",
    "sen sok": "Sen Sok", "sensok": "Sen Sok",
    "chroy changvar": "Chroy Changvar", "chroy changva": "Chroy Changvar",
    "mean chey": "Mean Chey", "meanchey": "Mean Chey",
    "chbar ampov": "Chbar Ampov", "chbar ompov": "Chbar Ampov",
    "prampir makara": "Prampir Makara", "7 makara": "Prampir Makara", "prampei makara": "Prampir Makara",
    "russey keo": "Russey Keo", "pou senchey": "Pou Senchey", "por senchey": "Pou Senchey", "posenchey": "Pou Senchey",
    "dangkao": "Dangkao", "prek pnov": "Prek Pnov", "preaek pnov": "Prek Pnov", "kamboul": "Kamboul",
    "phnom penh": "Phnom Penh",
    # Provinces
    "siem reap": "Siem Reap", "siemreap": "Siem Reap", "angkor": "Siem Reap",
    "battambang": "Battambang", "bat dambang": "Battambang",
    "sihanoukville": "Preah Sihanouk", "sihanouk": "Preah Sihanouk", "preah sihanouk": "Preah Sihanouk", "kampong som": "Preah Sihanouk",
    "kampot": "Kampot", "kep": "Kep",
    "kandal": "Kandal", "ta khmau": "Kandal", "takhmau": "Kandal",
    "kampong cham": "Kampong Cham", "tbong khmum": "Tboung Khmum", "tboung khmum": "Tboung Khmum",
    "poipet": "Banteay Meanchey", "poi pet": "Banteay Meanchey", "banteay meanchey": "Banteay Meanchey", "sisophon": "Banteay Meanchey",
    "bavet": "Svay Rieng", "svay rieng": "Svay Rieng",
    "koh kong": "Koh Kong", "pursat": "Pursat",
    "kampong chhnang": "Kampong Chhnang", "kampong speu": "Kampong Speu", "kampong thom": "Kampong Thom",
    "kratie": "Kratie", "takeo": "Takeo", "prey veng": "Prey Veng", "stung treng": "Stung Treng",
    "mondulkiri": "Mondulkiri", "ratanakiri": "Ratanakiri", "preah vihear": "Preah Vihear",
    "oddar meanchey": "Oddar Meanchey", "pailin": "Pailin",
}

# Dish and price benchmarks in USD
DISH_BENCHMARKS = [
    # Specific Khmer specialties
    (re.compile(r"(?:\b(?:kuy\s*teav|kuyteav)\b|គុយទាវ)", re.I), "kuy teav", "គុយទាវ", "2.50", "noodle;breakfast;soup;គុយទាវ"),
    (re.compile(r"(?:\b(?:bai\s*sach\s*chrouk|bay\s*sach\s*chrouk)\b|បាយសាច់ជ្រូក)", re.I), "bai sach chrouk", "បាយសាច់ជ្រូក", "2.00", "rice;pork;breakfast;បាយ"),
    (re.compile(r"(?:\b(?:lok\s*lak|loklak)\b|ឡុកឡាក់)", re.I), "lok lak", "ឡុកឡាក់", "4.50", "beef;stir_fry;dinner;ឡុកឡាក់"),
    (re.compile(r"(?:\b(?:num\s*banhchok|nom\s*banhchok)\b|នំបញ្ចុក|សម្លប្រហើរ)", re.I), "num banhchok", "នំបញ្ចុក", "2.00", "noodle;curry;traditional;នំបញ្ចុក"),
    (re.compile(r"(?:\b(?:amok|fish\s*amok)\b|អាម៉ុក|អាម៉ុកត្រី)", re.I), "amok", "អាម៉ុក", "5.00", "curry;fish;traditional;អាម៉ុក"),
    (re.compile(r"(?:\b(?:samlor\s*machu|samlar\s*machu)\b|សម្លម្ជូរ)", re.I), "samlor machu", "សម្លម្ជូរ", "3.50", "soup;sour;traditional;សម្ល"),
    (re.compile(r"(?:\b(?:samlor\s*kako|samlar\s*kako)\b|សម្លកកូរ)", re.I), "samlor kako", "សម្លកកូរ", "3.50", "soup;traditional;សម្ល"),
    (re.compile(r"(?:\b(?:bok\s*l['\s]?hong|tam\s*tam)\b|បុកល្ហុង)", re.I), "bok l'hong", "បុកល្ហុង", "2.50", "salad;spicy;street_food;បុកល្ហុង"),
    (re.compile(r"(?:\b(?:num\s*pang|nom\s*pang|baguette|sandwich|chrouk\s*kvai)\b|នំប៉័ង)", re.I), "num pang", "នំប៉័ង", "1.75", "sandwich;bread;street_food;នំប៉័ង"),
    (re.compile(r"(?:\b(?:banh\s*chhe?a?v|banh\s*chao)\b|បាញ់ឆែវ)", re.I), "banh chhev", "បាញ់ឆែវ", "2.50", "crepe;street_food;traditional;បាញ់ឆែវ"),
    (re.compile(r"(?:\b(?:lort\s*cha|lot\s*cha)\b|លតឆា)", re.I), "lort cha", "លតឆា", "2.25", "fried_noodles;street_food;លត"),
    (re.compile(r"(?:\b(?:mi\s*cha|mee\s*char)\b|មីឆា)", re.I), "mi cha", "មីឆា", "2.25", "fried_noodles;street_food;មី"),
    (re.compile(r"(?:\b(?:cha\s*kda[vo]|chha\s*kdao)\b|ឆាក្តៅ)", re.I), "cha kdao", "ឆាក្តៅ", "3.00", "khmer;spicy;stir_fry;ឆាក្តៅ"),
    (re.compile(r"(?:\b(?:mi\s*sour|mee\s*sour)\b|មីសួរ)", re.I), "mi sour", "មីសួរ", "2.50", "noodle;soup;khmer;មីសួរ"),
    (re.compile(r"(?:\b(?:mi\s*hel|mee\s*hal|spicy\s*noodle)\b|មីហឹរ)", re.I), "mi hel", "មីហឹរ", "2.75", "noodle;spicy;មីហឹរ"),
    (re.compile(r"(?:\b(?:bay\s*m[oa]i?n|bai\s*moan|chicken\s*rice)\b|បាយមាន់)", re.I), "chicken rice", "បាយមាន់", "2.50", "rice;chicken;breakfast;បាយ"),
    (re.compile(r"(?:\b(?:bai\s*cha|fried\s*rice)\b|បាយឆា)", re.I), "fried rice", "បាយឆា", "2.50", "rice;dinner;lunch;បាយ"),
    (re.compile(r"(?:\b(?:pt[eh]s\s*bay|ptah\s*bay|louk\s*bay|mhob\s*kamong|bay\s*bak)\b|បាយម្ហូបកុម្ម៉ង់|បាយកុម្ម៉ង់)", re.I), "Khmer Made-to-Order Dishes", "បាយម្ហូបកុម្ម៉ង់", "2.75", "rice;khmer;lunch;dinner;បាយ"),
    (re.compile(r"(?:\b(?:pleah\s*sach\s*ko)\b|ភ្លាសាច់គោ)", re.I), "pleah sach ko", "ភ្លាសាច់គោ", "4.50", "beef;salad;traditional;សាច់គោ"),
    (re.compile(r"(?:\b(?:sach\s*ko\s*jakak)\b|សាច់គោអាំង|សាច់គោចាក់កាក់)", re.I), "beef skewers", "សាច់គោអាំង", "3.00", "bbq;street_food;សាច់អាំង"),

    # Dining Styles & Special Categories
    (re.compile(r"(?:\b(?:buffet|all\s*you\s*can\s*eat)\b|ប៊ូហ្វេ)", re.I), "buffet", "អាហារប៊ូហ្វេ", "12.00", "buffet;all_you_can_eat;ប៊ូហ្វេ"),
    (re.compile(r"(?:\b(?:seafood|crab|shrimp|fish|prawn|squid|lobster)\b|គ្រឿងសមុទ្រ|ក្តាម|បង្គា|ត្រី|មឹក|បង្កង|ខ្យង|គ្រំ|ងាវ)", re.I), "seafood", "គ្រឿងសមុទ្រ", "8.00", "seafood;fish;dinner;គ្រឿងសមុទ្រ"),
    (re.compile(r"(?:\b(?:hot\s*pot|suki|soup|shabu|sukisoup)\b|ស៊ុប|ស៊ូគី)", re.I), "hot pot", "ស៊ុប", "8.00", "hotpot;soup;dinner;ស៊ុប"),
    (re.compile(r"(?:\b(?:bbq|barbecue|grill)\b|សាច់អាំង|អាំង)", re.I), "bbq", "សាច់អាំង", "5.50", "bbq;grill;dinner;សាច់អាំង"),

    # International
    (re.compile(r"(?:\b(?:sushi|japanese|sashimi|bento)\b|ម្ហូបជប៉ុន|ស៊ូស៊ី)", re.I), "japanese food", "ម្ហូបជប៉ុន", "8.50", "japanese;asian;sushi;ជប៉ុន"),
    (re.compile(r"(?:\b(?:korean|kimchi|k-bbq|bibimbap|samgyeopsal)\b|ម្ហូបកូរ៉េ)", re.I), "korean food", "ម្ហូបកូរ៉េ", "7.50", "korean;asian;bbq;កូរ៉េ"),
    (re.compile(r"(?:\b(?:chinese|dim\s*sum|dumpling|dumplings|peking\s*duck)\b|ម្ហូបចិន|ឌីមសាំ)", re.I), "chinese food", "ម្ហូបចិន", "5.50", "chinese;asian;dimsum;ចិន"),
    (re.compile(r"(?:\b(?:thai|tom\s*yum)\b|ម្ហូបថៃ)", re.I), "thai food", "ម្ហូបថៃ", "5.00", "thai;asian;spicy;ថៃ"),
    (re.compile(r"(?:\b(?:french|bistro)\b|ម្ហូបបារាំង)", re.I), "french food", "ម្ហូបបារាំង", "9.00", "french;western;bakery;បារាំង"),
    (re.compile(r"(?:\b(?:italian|lasagna)\b|ម្ហូបអ៊ីតាលី)", re.I), "italian food", "ម្ហូបអ៊ីតាលី", "7.50", "italian;western;pasta;អ៊ីតាលី"),
    (re.compile(r"(?:\b(?:indian|curry|tandoori|naan|biryani)\b|ម្ហូបឥណ្ឌា)", re.I), "indian food", "ម្ហូបឥណ្ឌា", "6.00", "indian;curry;halal;ឥណ្ឌា"),

    # Fast Food & Western
    (re.compile(r"(?:\b(?:pizza|pasta|spaghetti)\b|ភីហ្សា|ប៉ាស្តា)", re.I), "pizza", "ភីហ្សា", "7.50", "pizza;italian;fast_food;ភីហ្សា"),
    (re.compile(r"(?:\b(?:burger|hamburger)\b|ប៊ឺហ្គឺ)", re.I), "burger", "ប៊ឺហ្គឺ", "4.50", "burger;fast_food;western;ប៊ឺហ្គឺ"),
    (re.compile(r"(?:\b(?:fried\s*chicken|crispy\s*chicken|kfc|lotteria|texas\s*chicken)\b|មាន់បំពង)", re.I), "fried chicken", "មាន់បំពង", "4.00", "fast_food;chicken;មាន់បំពង"),

    # Beverages & Cafes
    (re.compile(r"(?:\b(?:coffee|cafe|café|espresso|cappuccino|latte|kfae|kafe|kofi|starbucks|brown\s*coffee|tube\s*coffee)\b|កាហ្វេ)", re.I), "coffee", "កាហ្វេ", "2.00", "cafe;beverage;coffee;កាហ្វេ"),
    (re.compile(r"(?:\b(?:bubble\s*tea|boba|milk\s*tea|matcha|chagee|dakasi|koi|an\s*cha)\b|តែគុជ|តែទឹកដោះគោ|តែបៃតង)", re.I), "bubble tea", "តែគុជ", "2.25", "tea;beverage;boba;តែគុជ"),
    (re.compile(r"(?:\b(?:yogurt|smoothie|shake|juice|fruit)\b|ទឹកក្រឡុក|ទឹកផ្លែឈើ|យ៉ាអួ)", re.I), "smoothie & juices", "ទឹកក្រឡុក និងទឹកផ្លែឈើ", "2.25", "juice;smoothie;yogurt;healthy;ភេសជ្ជៈ"),
    (re.compile(r"(?:\b(?:ice\s*cream|gelato|bingsoo|bingsu)\b|ការ៉េម|ប៊ីងស៊ូ)", re.I), "ice cream", "ការ៉េម", "2.50", "dessert;sweet;ice_cream;ការ៉េម"),

    # Bakery & Desserts
    (re.compile(r"(?:\b(?:bakery|cake|pastry|croissant|donut|doughnut|tous\s*les\s*jours|breadtalk)\b|នំខេក|បង្អែម|នំដុត)", re.I), "bakery", "នំប៉័ង", "2.00", "bakery;dessert;sweet;នំប៉័ង"),

    # General Noodles & Rice
    (re.compile(r"(?:\b(?:noodle|noodles|ramen|pho|udon|soup\s*mee)\b|មី|ហ្វឺ|រ៉ាមេន)", re.I), "noodles", "មី", "2.50", "noodles;asian;soup;មី"),
    (re.compile(r"(?:\b(?:vegetarian|vegan|plant\s*based)\b|ម្ហូបបួស)", re.I), "vegetarian food", "ម្ហូបបួស", "3.50", "vegetarian;healthy;vegan;ម្ហូបបួស"),
    (re.compile(r"(?:\b(?:fast\s*food)\b|អាហាររហ័ស)", re.I), "fast food", "អាហាររហ័ស", "4.00", "fast_food;chicken;អាហាររហ័ស"),
]

# Signature menu items for every food category
CATEGORY_SIGNATURE_ITEMS = [
    # Specific Khmer specialties
    (re.compile(r"kuy\s*teav|kuyteav|គុយទាវ|soup\s*mee", re.I),
     "Kuy Teav Phnom Penh, Beef Ball Noodle Soup, Seafood Rice Noodles, Pork Intestine Soup",
     "គុយទាវភ្នំពេញ គុយទាវប្រហិតសាច់គោ និងគុយទាវគ្រឿងសមុទ្រ"),
    (re.compile(r"num\s*banhchok|nom\s*banhchok|នំបញ្ចុក|nom\s*bonjok|somlor\s*khmer", re.I),
     "Nom Banh Chok with Green Fish Curry, Red Curry Noodle Soup, Fresh Vegetables",
     "នំបញ្ចុកសម្លប្រហើរ នំបញ្ចុកសម្លការី និងបន្លែស្រស់"),
    (re.compile(r"lort\s*cha|lot\s*cha|mi\s*cha|លតឆា|មីឆា", re.I),
     "Lort Cha with Fried Egg & Beef, Stir-Fried Egg Noodles (Mi Cha), Chive Cakes",
     "លតឆាសាច់គោពងទា មីឆា និងនំកាឆាយ"),
    (re.compile(r"bok\s*l['\s]?hong|បុកល្ហុង", re.I),
     "Spicy Papaya Salad (Bok Lhong) with Salted Crab, Grilled Chicken Wings, Sticky Rice",
     "បុកល្ហុងក្តាមប្រៃ ស្លាបមាន់អាំង និងបាយដំណើប"),
    (re.compile(r"banh\s*chhe?a?v|banh\s*chao|បាញ់ឆែវ", re.I),
     "Crispy Banh Chhev (Stuffed Rice Crepes) with Minced Pork, Shrimps & Fresh Herbs",
     "បាញ់ឆែវស្រួយ សាច់ជ្រូកចិញ្ច្រាំ និងបន្លែស្រស់"),
    (re.compile(r"num\s*pang|nom\s*pang|baguette|sandwich|នំប៉័ង|chrouk\s*kvai", re.I),
     "Num Pang Pate (Pork & Liver Pate Baguette), Roast Pork with Pickled Daikon & Herbs",
     "នំប៉័ងសាច់ប៉ាតេ នំប៉័ងសាច់ជ្រូកខ្វៃ និងជ្រក់បន្លែ"),
    (re.compile(r"cha[-_ ]?kda[vo]|chha[-_ ]?kdao|ឆាក្តៅ", re.I),
     "Cha Kdao (Spicy Holy Basil Stir-Fry with Chicken or Beef), Jasmine Rice",
     "ឆាក្តៅសាច់មាន់ ឆាក្តៅសាច់គោ និងបាយស"),
    (re.compile(r"mi[-_ ]?sour|mee[-_ ]?sour|មីសួរ", re.I),
     "Mi Sour (Khmer Glass Noodle Soup with Chicken and Mushrooms)",
     "មីសួរសាច់មាន់ និងស៊ុបផ្សិត"),
    (re.compile(r"mi[-_ ]?hel|mee[-_ ]?hal|spicy[-_ ]?noodle|មីហឹរ", re.I),
     "Spicy Level Noodles (Mi Hel 7 Levels) with Seafood, Beef and Meatballs",
     "មីហឹរ ៧ កម្រិត គ្រឿងសមុទ្រ និងសាច់គោ"),
    (re.compile(r"ramen|ramyeon|pho\b|noodle|មី", re.I),
     "Tonkotsu Pork Ramen, Vietnamese Beef Pho, Wonton Egg Noodle Soup",
     "រ៉ាមេនសាច់ជ្រូក ហ្វឺសាច់គោ និងមីគាវ"),

    # Dining Styles, BBQ & Hot Pot
    (re.compile(r"buffet|all\s*you\s*can\s*eat|ប៊ូហ្វេ", re.I),
     "All-You-Can-Eat Seafood, BBQ Beef & Pork, Fresh Oysters, Hot Pot, Salad Bar, Dessert",
     "អាហារប៊ូហ្វេគ្រឿងសមុទ្រ សាច់អាំង ស៊ុបឆ្នាំងដី និងបង្អែមច្រើនមុខ"),
    (re.compile(r"seafood|crab|shrimp|fish|prawn|squid|lobster|គ្រឿងសមុទ្រ|ក្តាម|បង្គា|ត្រី|មឹក|បង្កង", re.I),
     "Stir-Fried Crab with Fresh Kampot Green Peppercorns, Grilled River Prawns, Steamed Fish with Ginger",
     "ក្តាមថ្មឆាម្រេចខ្ចីកំពត បង្គាទន្លេអាំង និងត្រីចំហុយមីសួរខ្ញី"),
    (re.compile(r"hot\s*pot|suki|soup|ស៊ុប|shabu", re.I),
     "Claypot Suki Soup, Seafood Shabu Shabu, Sliced Australian Beef Hot Pot, Fresh Greens",
     "ស៊ុបឆ្នាំងដី ស៊ុបស៊ូគីគ្រឿងសមុទ្រ និងស៊ុបសាច់គោស្លាយ"),
    (re.compile(r"bbq|barbecue|grill|សាច់អាំង|sach\s*ko\s*jakak", re.I),
     "Grilled Beef Skewers (Sach Ko Ang), BBQ Pork Ribs, Grilled Chicken Wings, Pickled Papaya",
     "សាច់គោចាក់កាក់អាំង ឆ្អឹងជំនីជ្រូកអាំង និងជ្រក់ល្ហុង"),

    # Khmer Rice Dishes
    (re.compile(r"bai\s*sach|bay\s*sach|បាយសាច់ជ្រូក", re.I),
     "Bai Sach Chrouk (Marinated Grilled Pork with Broken Rice), Pickled Cucumbers, Clear Broth",
     "បាយសាច់ជ្រូកអាំង ជ្រក់ត្រសក់ និងទឹកស៊ុប"),
    (re.compile(r"lok\s*lak|ឡុកឡាក់", re.I),
     "Shaking Beef Lok Lak with Lime & Kampot Pepper Dip, Fried Egg, Steamed Rice",
     "ឡុកឡាក់សាច់គោ អំបិលម្រេចក្រូចឆ្មា ពងទាចៀន និងបាយស"),
    (re.compile(r"amok|អាម៉ុក", re.I),
     "Steamed Fish Amok in Banana Leaves, Khmer Red Chicken Curry, Jasmine Rice",
     "អាម៉ុកត្រីស្លឹកចេក ការីមាន់ខ្មែរ និងបាយក្រអូប"),
    (re.compile(r"bay\s*m[oa]i?n|bai\s*moan|chicken\s*rice|បាយមាន់", re.I),
     "Hainanese Steamed Chicken Rice, Roasted Village Chicken Rice with Ginger Sauce",
     "បាយមាន់ហៃណាំ និងបាយមាន់ស្រែទឹកត្រីខ្ញី"),
    (re.compile(r"ptes\s*bay|ptah\s*bay|louk\s*bay|mhob\s*kamong", re.I),
     "Khmer Made-to-Order Dishes: Beef Lok Lak, Pork with Rice, Seafood Fried Rice, Stir-Fried Morning Glory",
     "បាយម្ហូបកុម្ម៉ង់ ឡុកឡាក់សាច់គោ បាយសាច់ជ្រូក បាយឆា និងឆាត្រកួន"),

    # Beverages & Cafes
    (re.compile(r"coffee|cafe|café|espresso|cappuccino|latte|កាហ្វេ|kfae|kafe|kofi", re.I),
     "Cambodian Iced Milk Coffee (Kafe Toek Doh Ko), Iced Latte, Americano, Cold Brew, Passion Fruit Soda",
     "កាហ្វេទឹកដោះគោទឹកកក ឡាតេទឹកកក អាមេរិកាណូ និងកាហ្វេត្រជាក់"),
    (re.compile(r"bubble\s*tea|boba|milk\s*tea|matcha|តែគុជ|តែទឹកដោះគោ|chagee", re.I),
     "Brown Sugar Boba Milk Tea, Uji Matcha Latte, Jasmine Cheese Foam Tea, Mango Fruit Tea",
     "តែគុជស្ករក្រហម ម៉ាតឆាឡាតេ តែបៃតងហ្វូមឈីស និងតែផ្លែឈើស្រស់"),
    (re.compile(r"yogurt|smoothie|shake|juice|fruit|ទឹកក្រឡុក|យ៉ាអួ", re.I),
     "Fresh Avocado Smoothie, Passion Fruit Shake, Greek Yogurt Bowls, Cold-Pressed Juices",
     "ទឹកផ្លែបឺរក្រឡុក ទឹកក្រូចឆ្មាផាសិន យ៉ាអួផ្លែឈើ និងទឹកផ្លែឈើស្រស់"),

    # Western, Fast Food & Bakery
    (re.compile(r"burger|ប៊ឺហ្គឺ|fast\s*food", re.I),
     "Classic Cheeseburger, Crispy Fried Chicken Burger, Seasoned French Fries, Onion Rings",
     "ប៊ឺហ្គឺសាច់គោឈីស ប៊ឺហ្គឺមាន់បំពងស្រួយ និងដំឡូងបារាំងបំពង"),
    (re.compile(r"fried\s*chicken|crispy\s*chicken|មាន់បំពង", re.I),
     "Crispy Fried Chicken (Original / Spicy), Chicken Tenders, Fries, Coleslaw",
     "មាន់បំពងស្រួយរសជាតិហឹរ សាច់មាន់បន្ទះ និងដំឡូងបំពង"),
    (re.compile(r"pizza|pasta|spaghetti|ភីហ្សា|ម្ហូបអ៊ីតាលី|italian", re.I),
     "Wood-Fired Pizza (Margherita, Pepperoni), Creamy Pasta Carbonara, Spaghetti Bolognese",
     "ភីហ្សាដុតភ្លើងអុស ភីហ្សាភិបភើរ៉ូនី ប៉ាស្តាកាបូណារ៉ា និងស្ប៉ាហ្គេតទី"),
    (re.compile(r"bakery|cake|pastry|bread|croissant|dessert|នំប៉័ង|នំ|នំខេក", re.I),
     "French Butter Croissants, Fresh Baguettes, Chocolate Mousse Cake, Fruit Danish, Egg Tarts",
     "នំប៉័ងបារាំង ក្រូសង់ប៊័រ នំខេកសូកូឡា និងនំដេនីសផ្លែឈើ"),
    (re.compile(r"ice\s*cream|gelato|bingsoo|bingsu|ការ៉េម", re.I),
     "Artisan Gelato, Mango Bingsu (Korean Shaved Snow Ice), Waffle Sundae Bowls",
     "ការ៉េមជេឡាតូ ប៊ីងស៊ូផ្លែស្វាយ និងការ៉េមកែវធំ"),

    # BBQ & Hot Pot
    (re.compile(r"bbq|barbecue|grill|សាច់អាំង|sach\s*ko\s*jakak", re.I),
     "Grilled Beef Skewers (Sach Ko Ang), BBQ Pork Ribs, Grilled Chicken Wings, Pickled Papaya",
     "សាច់គោចាក់កាក់អាំង ឆ្អឹងជំនីជ្រូកអាំង និងជ្រក់ល្ហុង"),
    (re.compile(r"hot\s*pot|suki|soup|ស៊ុប|shabu", re.I),
     "Claypot Suki Soup, Seafood Shabu Shabu, Sliced Australian Beef Hot Pot, Fresh Greens",
     "ស៊ុបឆ្នាំងដី ស៊ុបស៊ូគីគ្រឿងសមុទ្រ និងស៊ុបសាច់គោស្លាយ"),

    # International & Specialty
    (re.compile(r"seafood|crab|shrimp|fish|គ្រឿងសមុទ្រ|ក្តាម|បង្គា|ត្រី", re.I),
     "Stir-Fried Crab with Fresh Kampot Green Peppercorns, Grilled River Prawns, Steamed Fish with Ginger",
     "ក្តាមថ្មឆាម្រេចខ្ចីកំពត បង្គាទន្លេអាំង និងត្រីចំហុយមីសួរខ្ញី"),
    (re.compile(r"sushi|japanese|sashimi|ម្ហូបជប៉ុន", re.I),
     "Fresh Salmon Sashimi, Spicy Tuna Roll, Chicken Teriyaki Bento, Tonkotsu Ramen",
     "សាស៊ីមីសាល់ម៉ុង ស៊ូស៊ី បាយប្រអប់តេរីយ៉ាគី និងរ៉ាមេន"),
    (re.compile(r"korean|kimchi|k-bbq|ម្ហូបកូរ៉េ", re.I),
     "Korean Grilled Pork Belly (Samgyeopsal), Stone-Bowl Bibimbap, Tteokbokki, Kimchi Jjigae",
     "សាច់ជ្រូកបីជាន់អាំងកូរ៉េ បាយឆាថ្មប៊ីប៊ីមបាប់ តុកបុកគី និងស៊ុបគីមឈី"),
    (re.compile(r"chinese|dim\s*sum|ម្ហូបចិន", re.I),
     "Steamed Pork Dumplings (Siu Mai), BBQ Pork Buns (Char Siu Bao), Peking Duck, Chow Mein",
     "ឌីមសាំគាវសាច់ជ្រូក នំប៉ាវសាច់ក្រហម ទាខ្វៃ និងមីឆាចិន"),
    (re.compile(r"thai|tom\s*yum|pad\s*thai|ម្ហូបថៃ", re.I),
     "Tom Yum Kung, Pad Thai Noodles, Som Tum Papaya Salad, Green Curry Chicken",
     "តុមយ៉ាំបង្គា ផាត់ថៃ បុកល្ហុងថៃ និងការីបៃតងសាច់មាន់"),
    (re.compile(r"vietnam|pho\b|banh\s*mi|ម្ហូបវៀតណាម", re.I),
     "Vietnamese Beef Pho Bo, Fresh Spring Rolls (Goi Cuon), Banh Mi Pate, Bun Cha",
     "ហ្វឺសាច់គោ គួងស្រស់វៀតណាម នំប៉័ងប៉ាតេ និងប៊ុនឆា"),
    (re.compile(r"italian|pizza|pasta|spaghetti|ម្ហូបអ៊ីតាលី|ភីហ្សា", re.I),
     "Wood-Fired Pizza (Margherita, Pepperoni), Creamy Pasta Carbonara, Spaghetti Bolognese",
     "ភីហ្សាដុតភ្លើងអុស ភីហ្សាភិបភើរ៉ូនី ប៉ាស្តាកាបូណារ៉ា និងស្ប៉ាហ្គេតទី"),
    (re.compile(r"french|bistro|ម្ហូបបារាំង", re.I),
     "French Steak Frites, Duck Confit, Classic Butter Croissants, French Onion Soup",
     "ស្តេកបារាំង ដំឡូងបំពង ទាចៀនក្រៀម និងក្រូសង់ប៊័រ"),
    (re.compile(r"mexican|taco|burrito|nachos|ម្ហូបម៉ិចស៊ិក", re.I),
     "Street Tacos (Carne Asada / Pollo), Loaded Burritos, Cheesy Quesadillas, Tortilla Chips & Guacamole",
     "តាកូសាច់គោ ប៊ូរីតូ ឈីសកេសាឌីយ៉ា និងណាចូស"),
    (re.compile(r"indian|curry|ម្ហូបឥណ្ឌា", re.I),
     "Butter Chicken Curry, Lamb Biryani with Raita, Garlic Naan, Vegetable Samosas",
     "ការីមាន់ប៊័រ បាយប៊ីរយ៉ានីសាច់ចៀម នំប៉័ងណាន និងសារម៉ូសា"),
    (re.compile(r"middle\s*eastern|kebab|shawarma|falafel|halal|អាហារហាឡាល់", re.I),
     "Chicken Shawarma Wrap, Beef Doner Kebab Plate, Crispy Falafel, Hummus with Pita",
     "សាច់សាវ៉ាម៉ា សាច់កេបាប់ ហ្វាឡាហ្វែល និងទឹកជ្រលក់ហ៊ូមូស"),
    (re.compile(r"steak|steakhouse|ស្តេក", re.I),
     "Grilled Australian Ribeye Steak, Tenderloin with Peppercorn Sauce, Mashed Potatoes",
     "ស្តេកសាច់គោអូស្ត្រាលី ទឹកជ្រលក់ម្រេច និងដំឡូងបារាំងកិន"),
    (re.compile(r"salad|healthy|poke|អាហារសុខភាព", re.I),
     "Salmon Poke Bowl with Edamame, Mediterranean Quinoa Salad, Avocado Greens Bowl",
     "ផូគីប៊ូលត្រីសាល់ម៉ុង សាឡាដគីណ័រ និងសាឡាដផ្លែបឺរ"),
    (re.compile(r"vegetarian|vegan|ម្ហូបបួស", re.I),
     "Tofu & Vegetable Stir-Fry, Fresh Spring Rolls with Peanut Dip, Vegetarian Amok, Garden Salad",
     "ឆាតៅហ៊ូបន្លែស្រស់ គួងបួសទឹកជ្រលក់សណ្តែកដី អាម៉ុកបួស និងសាឡាដ"),
]

def get_signature_items(text: str) -> tuple[str, str]:
    for pat, sig_en, sig_kh in CATEGORY_SIGNATURE_ITEMS:
        if pat.search(text):
            return sig_en, sig_kh
    return (
        "Khmer Made-to-Order Dishes: Beef Lok Lak, Pork with Rice, Fried Rice, Stir-Fried Morning Glory",
        "បាយម្ហូបកុម្ម៉ង់ ឡុកឡាក់សាច់គោ បាយសាច់ជ្រូក បាយឆា និងឆាត្រកួន"
    )

CUISINE_IMAGE_MAP = {
    "noodles": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?w=600&auto=format&fit=crop&q=80",
    "rice": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=600&auto=format&fit=crop&q=80",
    "curry": "https://images.unsplash.com/photo-1455619452474-d2be8b1e70cd?w=600&auto=format&fit=crop&q=80",
    "coffee": "https://images.unsplash.com/photo-1517256064527-09c73fc73e38?w=600&auto=format&fit=crop&q=80",
    "tea": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?w=600&auto=format&fit=crop&q=80",
    "pizza": "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=600&auto=format&fit=crop&q=80",
    "burger": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=600&auto=format&fit=crop&q=80",
    "chicken": "https://images.unsplash.com/photo-1626082927389-6cd097cdc6ec?w=600&auto=format&fit=crop&q=80",
    "bbq": "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?w=600&auto=format&fit=crop&q=80",
    "seafood": "https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?w=600&auto=format&fit=crop&q=80",
    "sushi": "https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=600&auto=format&fit=crop&q=80",
    "korean": "https://images.unsplash.com/photo-1590301157890-4810ed352733?w=600&auto=format&fit=crop&q=80",
    "bakery": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=600&auto=format&fit=crop&q=80",
    "hotpot": "https://images.unsplash.com/photo-1547592180-85f173990554?w=600&auto=format&fit=crop&q=80",
    "vegetarian": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=600&auto=format&fit=crop&q=80",
    "general": "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=600&auto=format&fit=crop&q=80",
}

def assign_food_image(dish_en: str, dish_kh: str, name: str, tags: str, current_img: str) -> str:
    """Return high-resolution food photo URL corresponding to cuisine/dish."""
    if current_img and current_img.startswith("http") and not any(bad in current_img for bad in ["node/", "way/", "relation/", "openstreetmap"]):
        return current_img

    text = f"{dish_en} {dish_kh} {name} {tags}".lower()
    if any(k in text for k in ["kuy teav", "kuyteav", "noodle", "ramen", "pho", "mee", "មី", "គុយទាវ"]):
        return CUISINE_IMAGE_MAP["noodles"]
    elif any(k in text for k in ["pizza", "italian", "ភីហ្សា"]):
        return CUISINE_IMAGE_MAP["pizza"]
    elif any(k in text for k in ["burger", "ប៊ឺហ្គឺ"]):
        return CUISINE_IMAGE_MAP["burger"]
    elif any(k in text for k in ["chicken", "fried chicken", "មាន់បំពង"]):
        return CUISINE_IMAGE_MAP["chicken"]
    elif any(k in text for k in ["coffee", "cafe", "espresso", "latte", "cappuccino", "កាហ្វេ"]):
        return CUISINE_IMAGE_MAP["coffee"]
    elif any(k in text for k in ["tea", "bubble", "boba", "milk tea", "តែ", "តែគុជ"]):
        return CUISINE_IMAGE_MAP["tea"]
    elif any(k in text for k in ["seafood", "crab", "prawn", "shrimp", "fish", "គ្រឿងសមុទ្រ", "ក្តាម", "បង្គា", "មឹក"]):
        return CUISINE_IMAGE_MAP["seafood"]
    elif any(k in text for k in ["bbq", "grill", "barbecue", "sach ang", "សាច់អាំង"]):
        return CUISINE_IMAGE_MAP["bbq"]
    elif any(k in text for k in ["sushi", "japanese", "sashimi", "ស៊ូស៊ី", "ជប៉ុន"]):
        return CUISINE_IMAGE_MAP["sushi"]
    elif any(k in text for k in ["korean", "kimchi", "bibimbap", "កូរ៉េ"]):
        return CUISINE_IMAGE_MAP["korean"]
    elif any(k in text for k in ["amok", "curry", "num banhchok", "អាម៉ុក", "ការី", "នំបញ្ចុក"]):
        return CUISINE_IMAGE_MAP["curry"]
    elif any(k in text for k in ["bakery", "bread", "cake", "pastry", "croissant", "num pang", "នំប៉័ង", "នំ"]):
        return CUISINE_IMAGE_MAP["bakery"]
    elif any(k in text for k in ["soup", "hotpot", "hot pot", "suki", "shabu", "ស៊ុប"]):
        return CUISINE_IMAGE_MAP["hotpot"]
    elif any(k in text for k in ["rice", "bay sach", "lok lak", "បាយ", "ឡុកឡាក់"]):
        return CUISINE_IMAGE_MAP["rice"]
    elif any(k in text for k in ["vegetarian", "vegan", "salad", "បួស"]):
        return CUISINE_IMAGE_MAP["vegetarian"]
    else:
        return CUISINE_IMAGE_MAP["general"]

KHMER_CHAR_RE = re.compile(r"[\u1780-\u17FF\u19E0-\u19FF]")

def normalize_area(area_str: str) -> str:
    if not area_str or area_str.strip().lower() == "cambodia":
        return ""                                    # unknown: say so, never pretend a place is somewhere
    val = area_str.strip().lower()
    for k, v in AREA_NORMALIZATION.items():
        if k in val:
            return v
    return area_str.strip().title()

def enrich_dish_and_price(name: str, desc: str, tags: str, dish_en: str, dish_kh: str, price_usd: str) -> tuple[str, str, str, str]:
    target_text = f"{name} {desc} {tags} {dish_en} {dish_kh}".strip()
    res_en, res_kh = dish_en.strip(), dish_kh.strip()
    res_price = price_usd.strip()
    extra_tags = []

    is_generic = not res_en or res_en.lower() in [
        "popular local dishes & drinks", "food venue", "unknown", "restaurant", "none", "nan", ""
    ]

    # Clean location boilerplate to prevent false matches from city/province names
    clean_target = re.sub(r"Restaurant in.*?\.", "", target_text)
    clean_target = re.sub(r"ភោជនីយដ្ឋាននៅ.*?(?:ភ្នំពេញ|រាជធានី|ខេត្ត).*?។", "", clean_target)
    clean_target = re.sub(r"\b(?:phnom\s*penh|siem\s*reap|battambang|sihanoukville|kampot|kandal)\b", "", clean_target, flags=re.I)
    clean_target = re.sub(r"(?:ភ្នំពេញ|សៀមរាប|បាត់ដំបង|ព្រះសីហនុ|កំពត|កណ្តាល)", "", clean_target)

    for pat, canonical_en, canonical_kh, default_price, tag_str in DISH_BENCHMARKS:
        if pat.search(clean_target):
            if is_generic:
                res_en = canonical_en
                res_kh = canonical_kh
            elif not res_en:
                res_en = canonical_en
            if not res_kh:
                res_kh = canonical_kh
            extra_tags.extend(tag_str.split(";"))      # (no default price: a price must come from the source)
            is_generic = False
            break

    # Still generic: the dish is unknown, so it stays empty (no invented "made-to-order dishes")
    if is_generic and res_en.lower() in ["popular local dishes & drinks", "food venue", "unknown", "none", "nan"]:
        res_en, res_kh = "", res_kh

    # If dish_en is known, lookup dish_kh and price
    if res_en:
        for _, canonical_en, canonical_kh, default_price, tag_str in DISH_BENCHMARKS:
            if canonical_en.lower() == res_en.lower():
                if not res_kh:
                    res_kh = canonical_kh
                extra_tags.extend(tag_str.split(";"))
                break

    all_tags = set(tags.split(";")) if tags else set()
    all_tags.update(extra_tags)
    clean_tags = ";".join([t.strip() for t in all_tags if t.strip()])

    return res_en, res_kh, res_price, clean_tags

def build_conversational_description(name: str, dish_en: str, dish_kh: str, price_usd: str,
                                     area: str, phone: str, page_url: str,
                                     open_h: str, close_h: str, existing_desc: str,
                                     tags: str = "") -> str:
    """Build rich conversational notes answering: dish, price, location, how to order/contact, hours, signature menu items."""
    parts = []
    
    # 1. Location and identity
    dish_str = f"serving {dish_en} ({dish_kh})" if dish_en and dish_kh else (f"serving {dish_en}" if dish_en else "food venue")
    where = f"{area}, Cambodia" if area else "Cambodia"
    parts.append(f"{dish_str.capitalize()} in {where}.")
    if dish_kh:
        parts.append(f"មានបម្រើ {dish_kh}" + (f" នៅ{area}។" if area else "។"))

    # 2. Price statement, only when the source gave a price (no estimates)
    if price_usd:
        try:
            p_val = float(price_usd)
            khr_val = int(round(p_val * 4100, -2))
            parts.append(f"Price: about ${p_val:.2f} ({khr_val:,} Riel). តម្លៃប្រហែល ${p_val:.2f} (ឬ {khr_val:,} រៀល)។")
        except ValueError:
            parts.append(f"Price: {price_usd}.")

    # 3. (no "popular menu items": a menu must come from the place or its page, never from its category)

    # 4. How to order / contact / reserve ('how to it else' query)
    order_modes = []
    if phone:
        order_modes.append(f"Call {phone} for takeout or reservations (ទូរស័ព្ទ៖ {phone})")
    if page_url:
        order_modes.append(f"Order online / view menu at {page_url}")
    if order_modes:
        parts.append(f"How to order: {'; '.join(order_modes)}.")

    # 5. Hours ("11.5" -> "11:30")
    if open_h and close_h:
        try:
            clock = lambda h: f"{int(float(h)) % 24:02d}:{round(float(h) % 1 * 60):02d}"
            parts.append(f"Open: {clock(open_h)}-{clock(close_h)} (ម៉ោងបើកលក់៖ {clock(open_h)} ដល់ {clock(close_h)})។")
        except ValueError:
            pass

    # 6. Keep any unique existing notes
    if existing_desc and len(existing_desc) > 20:
        cleaned_orig = re.sub(r"Restaurant in.*?\.", "", existing_desc)
        cleaned_orig = TEMPLATE_SENTENCE_RE.sub(" ", cleaned_orig)
        cleaned_orig = re.sub(r"\s+", " ", cleaned_orig).strip()
        if len(cleaned_orig) > 15 and cleaned_orig not in " ".join(parts):
            parts.append(cleaned_orig[:300])

    return " ".join(parts)

def name_key(s: str) -> str:
    if not s or not isinstance(s, str):
        return ""
    cleaned = re.sub(r"[^a-zA-Z0-9\u1780-\u17FF]+", "", s).lower()
    for stop in ["restaurant", "cafe", "cambodia", "phnompenh", "siemreap", "ហាង", "ភោជនីយដ្ឋាន"]:
        cleaned = cleaned.replace(stop, "")
    return cleaned.strip()

def merge_and_normalize(sources: list[str] = None, output_file: str = "data/scraped/restaurants_combined.csv") -> pd.DataFrame:
    if sources is None:
        sources = [
            "data/scraped/canby_places.csv",
            "data/scraped/yellowpages_places.csv",
            "data/scraped/foodchow_places.csv",
            "data/scraped/wownow_deals.csv",
            "data/scraped/foodpanda_places.csv",
            "data/scraped/grabfood_categories.csv",
            "data/scraped/wikidata_dishes.csv",
            "data/scraped/osm_places.csv",
            "data/scraped/overture_places.csv",
        ]

    dfs = []
    for s_path in sources:
        p = Path(s_path)
        if p.exists() and p.stat().st_size > 100:
            try:
                df = pd.read_csv(p, dtype=str, keep_default_na=False)
                if "image_url" not in df.columns and "image_path" in df.columns:
                    df["image_url"] = df["image_path"]
                elif "image_path" not in df.columns and "image_url" in df.columns:
                    df["image_path"] = df["image_url"]
                for col in DATA_COLUMNS:
                    if col not in df.columns:
                        df[col] = ""
                dfs.append(df[DATA_COLUMNS])
                print(f"Loaded {len(df)} rows from {p.name}")
            except Exception as e:
                print(f"Could not load {p.name}: {e}")

    if not dfs:
        print("No source datasets found.")
        return pd.DataFrame(columns=DATA_COLUMNS)

    combined = pd.concat(dfs, ignore_index=True)
    print(f"Total raw records from all sources: {len(combined)}")

    for col in DATA_COLUMNS:
        combined[col] = combined[col].fillna("").astype(str).str.strip()

    # 0. Facts only: drop non-places, clear guessed values (see GUESSED_FIELDS)
    combined = keep_facts_only(combined).reset_index(drop=True)

    # 1. Normalize Area (Nationwide Cambodia + Khans)
    combined["area"] = combined["area"].apply(normalize_area)

    # 2. Enrich dishes and prices
    for idx, row in combined.iterrows():
        d_en, d_kh, p_usd, enriched_tags = enrich_dish_and_price(
            row["name"], row["description"], row["tags"], row["dish_en"], row["dish_kh"], row["price_usd"]
        )
        combined.at[idx, "dish_en"] = d_en
        combined.at[idx, "dish_kh"] = d_kh
        combined.at[idx, "price_usd"] = p_usd
        combined.at[idx, "tags"] = enriched_tags

    # 3. Deduplicate across sources
    combined["_key"] = combined["name"].apply(name_key)
    records = []
    seen_keys = {}

    for _, row in combined.iterrows():
        key = row["_key"]
        if not key or len(key) < 3:
            records.append(row[DATA_COLUMNS].to_dict())
            continue

        if key in seen_keys:
            existing = seen_keys[key]
            # Merge bilingual names
            if not KHMER_CHAR_RE.search(existing["name"]) and KHMER_CHAR_RE.search(row["name"]):
                existing["name"] = f"{existing['name']} ({row['name']})"
            elif KHMER_CHAR_RE.search(existing["name"]) and not KHMER_CHAR_RE.search(row["name"]):
                existing["name"] = f"{row['name']} ({existing['name']})"

            # Merge fields
            for col in ["dish_en", "dish_kh", "price_usd", "lat", "lng", "rating", "open_hour", "close_hour", "phone_public", "page_url", "image_url", "image_path", "menu"]:
                if not existing[col] and row[col]:
                    existing[col] = row[col]

            # Merge tags
            existing_tags = set(existing["tags"].split(";")) if existing["tags"] else set()
            new_tags = set(row["tags"].split(";")) if row["tags"] else set()
            existing["tags"] = ";".join([t for t in (existing_tags | new_tags) if t])

            if row["source"] not in existing["source"]:
                existing["source"] = f"{existing['source']};{row['source']}"
        else:
            rec = row[DATA_COLUMNS].to_dict()
            seen_keys[key] = rec
            records.append(rec)

    final_df = pd.DataFrame(records)[DATA_COLUMNS]

    # A WOWNOW post that no other source confirms is a promotion ("MEGA SALE", "Enjoy up to"), not a place: no address,
    # location, phone or hours, and its price is a deal price. Brands that OpenStreetMap or Overture also list stay.
    promo_only = final_df["source"].str.lower().eq("wownow-telegram")
    print(f"Facts only: dropped {int(promo_only.sum())} WOWNOW promotion posts that no other source confirms as a place")
    final_df = final_df[~promo_only].reset_index(drop=True)

    # 4. Generate conversational descriptions from the known facts (no stock photos: a photo must show the place)
    for idx, row in final_df.iterrows():
        conv_desc = build_conversational_description(
            name=row["name"],
            dish_en=row["dish_en"],
            dish_kh=row["dish_kh"],
            price_usd=row["price_usd"],
            area=row["area"],
            phone=row["phone_public"],
            page_url=row["page_url"],
            open_h=row["open_hour"],
            close_h=row["close_hour"],
            existing_desc=row["description"],
            tags=row["tags"],
        )
        final_df.at[idx, "description"] = conv_desc
    final_df["description"] = final_df["description"].map(unique_sentences)     # the notes may repeat the source text

    # Save output
    out_p = Path(output_file)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(out_p, index=False)
    print(f"✅ Saved nationwide conversational dataset: {len(final_df)} records -> {out_p}")

    # Generate nationwide quality stats
    has_khmer = final_df["name"].str.contains(KHMER_CHAR_RE) | final_df["dish_kh"].ne("") | final_df["description"].str.contains(KHMER_CHAR_RE)
    has_english = final_df["name"].str.contains(r"[A-Za-z]") | final_df["dish_en"].ne("")
    has_price = final_df["price_usd"].ne("")
    has_contact = final_df["phone_public"].ne("") | final_df["page_url"].ne("")
    has_coords = final_df["lat"].ne("") & final_df["lng"].ne("")
    has_hours = final_df["open_hour"].ne("")
    has_image = final_df["image_url"].str.startswith("http") | final_df["image_path"].str.startswith("http")

    print("\n--- Nationwide Cambodia Dataset Quality Report ---")
    print(f"Total Unique Places:                {len(final_df)}")
    print(f"Food Image Coverage:                {has_image.mean():.1%} ({has_image.sum()} places)")
    print(f"Price Coverage (USD):               {has_price.mean():.1%} ({has_price.sum()} places)")
    print(f"Ordering / Contact Coverage:        {has_contact.mean():.1%} ({has_contact.sum()} places)")
    print(f"Khmer Content Coverage:             {has_khmer.mean():.1%} ({has_khmer.sum()} places)")
    print(f"English Content Coverage:           {has_english.mean():.1%} ({has_english.sum()} places)")
    print(f"Operating Hours:                    {has_hours.mean():.1%} ({has_hours.sum()} places)")
    print(f"GPS Coordinates:                    {has_coords.mean():.1%} ({has_coords.sum()} places)")
    print("\nTop Areas / Provinces:")
    print(final_df["area"].value_counts().head(15).to_string())

    return final_df

if __name__ == "__main__":
    merge_and_normalize()

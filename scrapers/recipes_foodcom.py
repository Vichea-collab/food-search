"""
Build data/recipes.csv: one recipe per Food-101 dish (the 101 dishes the photo classifier knows),
with ingredients, steps, prep / cook / total minutes and servings, from Food.com recipes.

Two public copies of the same Food.com recipes, joined on the Food.com recipe id:
  STEPS  RecipeNLG (Bień et al., INLG 2020), Hugging Face "Mahimas/recipenlg": title, directions, link.
         Only the ~500k Food.com rows are kept (link www.food.com/recipe/<slug>-<id>).
         Its ingredient lines have scraping errors ("13 cup sugar" for 1/3 cup), so they are not used.
  FACTS  Food.com crawl (Kaggle "Food.com Recipes and Reviews"), Hugging Face "Karo8870/food.com-parsed-dataset":
         prep and cook minutes, servings, calories, ingredients as {quantity, unit, name}, photo links.
         Its steps column is broken (photo links or empty), and the recipe id only appears inside the photo links
         (.../img/recipes/65/42/9/pic.jpg -> 65429), so only recipes with a photo can be joined (~147k).
The join is checked: the two titles agree for 94% of joined recipes (the rest differ in case or punctuation).

Choosing one recipe per dish: candidates whose title contains the dish name, scored to prefer the plain version
of the dish (no "vegan / crock pot / copycat ..."), a normal number of steps, a realistic time, and popularity
(number of user photos on Food.com; the copies have no ratings). PICKS pins a recipe by id where the score chose
badly; every pick was read by hand with --review.

Usage (needs pyarrow: pip install pyarrow):
    python scrapers/recipes_foodcom.py --review     # the 3 best candidates per dish
    python scrapers/recipes_foodcom.py              # write data/recipes.csv
Downloads (~450 MB after keeping only Food.com rows) go to data/raw/foodcom/ (git-ignored).
"""

import argparse
import html
import json
import math
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "foodcom"
OUT = ROOT / "data" / "recipes.csv"
HF_API = "https://huggingface.co/api/datasets/{repo}/parquet/default/train"
STEPS_REPO, FACTS_REPO = "Mahimas/recipenlg", "Karo8870/food.com-parsed-dataset"

# Food-101 class id -> recipe titles to look for (first = preferred). The ids match the classifier's classes.
DISHES = {
    "apple_pie": ["apple pie"], "baby_back_ribs": ["baby back ribs"], "baklava": ["baklava"],
    "beef_carpaccio": ["beef carpaccio", "carpaccio"], "beef_tartare": ["steak tartare", "beef tartare", "tartare"],
    "beet_salad": ["beet salad", "beetroot salad"], "beignets": ["beignets", "beignet"],
    "bibimbap": ["bibimbap", "bi bim bap"], "bread_pudding": ["bread pudding"],
    "breakfast_burrito": ["breakfast burritos", "breakfast burrito"], "bruschetta": ["bruschetta"],
    "caesar_salad": ["caesar salad"], "cannoli": ["cannoli"], "caprese_salad": ["caprese salad", "insalata caprese"],
    "carrot_cake": ["carrot cake"], "ceviche": ["ceviche"], "cheese_plate": ["cheese platter", "cheese plate", "cheese board"],
    "cheesecake": ["cheesecake"], "chicken_curry": ["chicken curry"],
    "chicken_quesadilla": ["chicken quesadillas", "chicken quesadilla"], "chicken_wings": ["chicken wings", "buffalo wings"],
    "chocolate_cake": ["chocolate cake"], "chocolate_mousse": ["chocolate mousse"], "churros": ["churros"],
    "clam_chowder": ["new england clam chowder", "clam chowder"], "club_sandwich": ["club sandwich"],
    "crab_cakes": ["crab cakes"], "creme_brulee": ["creme brulee"], "croque_madame": ["croque madame", "croque monsieur"],
    "cup_cakes": ["vanilla cupcakes", "cupcakes"], "deviled_eggs": ["deviled eggs"], "donuts": ["doughnuts", "donuts"],
    "dumplings": ["chinese dumplings", "pork dumplings", "dumplings"], "edamame": ["edamame"],
    "eggs_benedict": ["eggs benedict"], "escargots": ["escargots", "escargot"], "falafel": ["falafel"],
    "filet_mignon": ["filet mignon"], "fish_and_chips": ["fish and chips", "fish n chips", "fish chips"],
    "foie_gras": ["foie gras"], "french_fries": ["french fries"], "french_onion_soup": ["french onion soup"],
    "french_toast": ["french toast"], "fried_calamari": ["fried calamari", "calamari"], "fried_rice": ["fried rice"],
    "frozen_yogurt": ["frozen yogurt"], "garlic_bread": ["garlic bread"], "gnocchi": ["potato gnocchi", "gnocchi"],
    "greek_salad": ["greek salad"], "grilled_cheese_sandwich": ["grilled cheese sandwich", "grilled cheese"],
    "grilled_salmon": ["grilled salmon"], "guacamole": ["guacamole"], "gyoza": ["gyoza", "potstickers"],
    "hamburger": ["hamburgers", "hamburger", "burgers"], "hot_and_sour_soup": ["hot and sour soup"],
    "hot_dog": ["hot dogs", "hot dog"], "huevos_rancheros": ["huevos rancheros"], "hummus": ["hummus"],
    "ice_cream": ["vanilla ice cream", "ice cream"], "lasagna": ["lasagna"], "lobster_bisque": ["lobster bisque"],
    "lobster_roll_sandwich": ["lobster rolls", "lobster roll"],
    "macaroni_and_cheese": ["macaroni and cheese", "mac and cheese"], "macarons": ["french macarons", "macarons"],
    "miso_soup": ["miso soup"], "mussels": ["steamed mussels", "mussels"], "nachos": ["nachos"],
    "omelette": ["omelette", "omelet"], "onion_rings": ["onion rings"], "oysters": ["oysters"],
    "pad_thai": ["pad thai"], "paella": ["paella"], "pancakes": ["pancakes"], "panna_cotta": ["panna cotta"],
    "peking_duck": ["peking duck"], "pho": ["pho"], "pizza": ["pizza"], "pork_chop": ["pork chops", "pork chop"],
    "poutine": ["poutine"], "prime_rib": ["prime rib"], "pulled_pork_sandwich": ["pulled pork sandwiches", "pulled pork"],
    "ramen": ["ramen"], "ravioli": ["ravioli"], "red_velvet_cake": ["red velvet cake"], "risotto": ["risotto"],
    "samosa": ["samosas", "samosa"], "sashimi": ["sashimi"], "scallops": ["seared scallops", "scallops"],
    "seaweed_salad": ["seaweed salad"], "shrimp_and_grits": ["shrimp and grits"],
    "spaghetti_bolognese": ["spaghetti bolognese", "bolognese"], "spaghetti_carbonara": ["spaghetti carbonara", "carbonara"],
    "spring_rolls": ["spring rolls"], "steak": ["steak"], "strawberry_shortcake": ["strawberry shortcake"],
    "sushi": ["sushi"], "tacos": ["tacos"], "takoyaki": ["takoyaki"], "tiramisu": ["tiramisu"],
    "tuna_tartare": ["tuna tartare", "ahi tartare"], "waffles": ["waffles"],
}

# Food.com recipe ids picked by hand where the automatic choice was not the plain dish (see --review).
PICKS = {
    "baby_back_ribs": "179093",        # top pick needed 9 hours of marinating
    "beef_carpaccio": "73858",         # the plain "beef carpaccio" title exists twice: not joinable
    "beef_tartare": "34791",           # Swedish steak tartare (no plain French version on Food.com)
    "cannoli": "236331",               # top pick was the filling only (2 steps, 5 minutes)
    "chicken_wings": "28822",          # buffalo wings: the Food-101 photos are mostly these
    "dumplings": "288424",             # siu mai: Food-101 "dumplings" are Asian, the top pick was American drop dumplings
    "filet_mignon": "487364",          # more cooked (7 photos) than the 1-photo top pick
    "foie_gras": "323919",             # seared foie gras (top pick was a peanut-butter sandwich)
    "frozen_yogurt": "35079",
    "oysters": "356177",               # freshly shucked oysters with mignonette, like the Food-101 photos
    "pho": "288381",                   # pho bo, Vietnamese beef noodle soup
    "pizza": "22754",                  # homemade dough and toppings, 8 photos
    "pulled_pork_sandwich": "362125",  # the top pick started from already cooked pork
    "ramen": "532074",                 # pork belly ramen (other titles use instant noodles in other dishes)
    "risotto": "287395",
}
NO_RECIPE = {"sashimi", "takoyaki"}   # no proper recipe with times on Food.com: the app says so

NICE_NAMES = {"caesar_salad": "Caesar salad", "creme_brulee": "Crème brûlée", "eggs_benedict": "Eggs Benedict",
              "french_fries": "French fries", "french_onion_soup": "French onion soup", "french_toast": "French toast",
              "greek_salad": "Greek salad", "pho": "Pho", "beef_carpaccio": "Beef carpaccio"}

# Words that turn the dish into something else (a variant, another dish, a drink)
VARIANT = re.compile(
    r"\b(vegan|vegetarian|veggie|low ?fat|low ?carb|lite|light|lighter|skinny|healthy|healthier|diabetic|gluten ?free|"
    r"sugar ?free|dairy ?free|paleo|keto|crock ?pot|crockpot|slow cooker|copycat|ww|weight watchers|bread machine|abm|"
    r"microwave|dogs?|kids|cookies?|bars?|muffins?|dip|casserole|soup|salad|sandwich|wraps?|pie|cake|cupcakes?|"
    r"drink|shots?|cocktail|martini|liqueur|smoothie|shake|popsicles?|fudge|bites|cups|squares|bake|seasoning|sauce|"
    r"mix|dressing|leftover|stuffed|style|faux|mock|fake|imitation|frosting|icing|bread|pizza|burgers?|tacos?|"
    r"breakfast|dessert|fruit|chocolate|pumpkin|banana|peanut|tofu|turkey|chips|rolls?|pasta|noodles?|rice|eggs?|"
    r"quesadillas?|nachos|pancakes?|waffles?|scones?|ice cream|cheesecake|brownies?|dough|crust|ii|iii|iv)\b")
PLAIN = {"classic", "traditional", "authentic", "basic", "easy", "best", "perfect", "homemade", "simple", "the",
         "real", "old", "fashioned", "my", "s", "a", "and", "with", "de", "la", "le", "quick", "ever", "really",
         "good", "great", "delicious", "favorite", "original", "famous", "ultimate", "all", "american", "style"}


def display_name(c: str) -> str:
    return NICE_NAMES.get(c, c.replace("_", " ").capitalize())


def norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def parquet_urls(repo: str) -> list:
    return json.load(urllib.request.urlopen(HF_API.format(repo=repo)))


def download_steps() -> list:
    """RecipeNLG, one file at a time, keeping only Food.com rows (the full set is 2.3 GB)."""
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    RAW.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, url in enumerate(parquet_urls(STEPS_REPO)):
        path = RAW / f"nlg_{i}.parquet"
        if not path.exists():
            print("downloading", url)
            tmp = RAW / "_part.parquet"
            urllib.request.urlretrieve(url, tmp)
            t = pq.read_table(tmp, columns=["title", "directions", "link"])
            pq.write_table(t.filter(pc.match_substring(t["link"], "food.com/recipe")), path)
            tmp.unlink()
        paths.append(path)
    return paths


def download_facts() -> list:
    RAW.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, url in enumerate(parquet_urls(FACTS_REPO)):
        path = RAW / f"a_{i}.parquet"
        if not path.exists():
            print("downloading", url)
            urllib.request.urlretrieve(url, path)
        paths.append(path)
    return paths


def load() -> pd.DataFrame:
    steps = pd.concat([pd.read_parquet(p, columns=["title", "directions", "link"]) for p in download_steps()])
    steps["recipe_id"] = steps["link"].str.extract(r"-(\d+)\s*$")[0]
    facts = pd.concat([pd.read_parquet(p, columns=["name", "cooking_time", "preparation_time", "description", "servings",
                                                   "ingredients", "calories", "images", "tags"])
                       for p in download_facts()])
    facts = facts.reset_index(drop=True)
    facts["recipe_id"] = facts["images"].astype(str).str.extract(r"/img/recipes/((?:\d+/)+)")[0].str.replace("/", "")
    facts = facts[facts.recipe_id.isna() | ~facts.recipe_id.duplicated()]
    steps = steps.dropna(subset=["recipe_id"]).drop_duplicates("recipe_id")
    by_id = steps.merge(facts, on="recipe_id", how="inner")
    # Recipes without a photo have no id in FACTS: join those on the title, only when it is unique on both sides
    steps["t"], facts["t"] = steps["title"].map(norm), facts["name"].map(norm)
    rest = steps[~steps.recipe_id.isin(by_id.recipe_id) & ~steps.duplicated("t", keep=False)]
    facts_u = facts.drop_duplicates("t", keep=False).drop(columns="recipe_id")
    by_title = rest.merge(facts_u, on="t", how="inner").drop(columns="t")
    d = pd.concat([by_id.assign(joined_on="id"), by_title.assign(joined_on="title")], ignore_index=True)
    d["steps"] = d["directions"].map(json.loads)
    d["n_steps"] = d["steps"].map(len)
    d["n_photos"] = d["images"].map(lambda s: len(json.loads(s)) if isinstance(s, str) and s.startswith("[") else 0)
    d["total"] = d["preparation_time"] + d["cooking_time"]
    d["name_n"] = d["title"].map(norm)
    print(f"Food.com recipes with steps + times + ingredients: {len(d):,} "
          f"({(d.joined_on == 'id').sum():,} joined on the recipe id, {(d.joined_on == 'title').sum():,} on a unique title)")
    return d


def score(row, query: str) -> float:
    extra = [w for w in row.name_n.split() if w not in query.split() and w not in PLAIN]
    s = 100.0 if row.name_n == query else 90.0 if not extra else 60.0 - 8 * len(extra)
    s -= 40 * bool(VARIANT.search(" ".join(extra)))
    s += min(30.0, 6 * math.log2(1 + row.n_photos))               # popularity: user photos on Food.com
    s += 10 * (3 <= row.n_steps <= 15) - 15 * (row.n_steps > 20) - 25 * (row.n_steps < 2)
    s -= 40 * (row.total <= 0 or row.total > 12 * 60)
    return s


def candidates(d: pd.DataFrame, dish: str) -> pd.DataFrame:
    found = []
    for rank, query in enumerate(DISHES[dish]):
        hit = d[d.name_n.str.contains(rf"\b{re.escape(query)}\b", regex=True)].copy()
        if len(hit):
            hit["score"] = hit.apply(score, axis=1, query=query) - 5 * rank
            found.append(hit)
    if not found:
        return pd.DataFrame()
    return pd.concat(found).drop_duplicates("recipe_id").sort_values("score", ascending=False)


def ingredient_lines(raw) -> list:
    lines = []
    for item in json.loads(raw) if isinstance(raw, str) and raw.startswith("[") else []:
        text = re.sub(r"\s+", " ", " ".join(str(item.get(k) or "").strip() for k in ("quantity", "unit", "name"))).strip()
        if item.get("description"):
            text += f", {item['description']}"
        if text:
            lines.append(text)
    return lines


def tidy(s: str) -> str:
    s = re.sub(r"\s+", " ", html.unescape(str(s))).strip()
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    return s[:1].upper() + s[1:]


BOILERPLATE = re.compile(r"^\s*Make and share this .* recipe from Food\.com\.?\s*$", re.I)


def clean_title(r) -> str:
    title = tidy(r["name"] if isinstance(r["name"], str) else r.title)
    return re.sub(r"\.{2,}\s*", " - ", title).strip("\"' ")


def difficulty(n_steps: int, total: int) -> str:
    if n_steps <= 6 and total <= 45:
        return "easy"
    if n_steps >= 12 or total >= 120:
        return "hard"
    return "medium"


def build(d: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for dish in DISHES:
        if dish in NO_RECIPE:
            continue
        cand = d[d.recipe_id == PICKS[dish]] if dish in PICKS else candidates(d, dish)
        if cand.empty:
            print(f"  ⚠️ no recipe for {dish}")
            continue
        r = cand.iloc[0]
        rows.append({
            "dish_id": dish, "dish_name": display_name(dish), "recipe_title": clean_title(r),
            "description": "" if not isinstance(r.description, str) or BOILERPLATE.match(r.description)
                           else tidy(r.description),
            "ingredients": json.dumps(ingredient_lines(r.ingredients), ensure_ascii=False),
            "steps": json.dumps([tidy(s) for s in r.steps if str(s).strip()], ensure_ascii=False),
            "prep_minutes": int(r.preparation_time), "cook_minutes": int(r.cooking_time), "total_minutes": int(r.total),
            "servings": int(r.servings) if pd.notna(r.servings) else None,
            "calories_per_serving": round(float(r.calories)) if pd.notna(r.calories) else None,
            "difficulty": difficulty(int(r.n_steps), int(r.total)),
            "source": "Food.com", "source_url": f"https://{r.link.strip()}", "recipe_id": r.recipe_id,
        })
    out = pd.DataFrame(rows)
    for col in ("servings", "calories_per_serving"):
        out[col] = out[col].astype("Int64")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review", action="store_true", help="print the 3 best candidates per dish and exit")
    ap.add_argument("--top", type=int, default=3)
    args = ap.parse_args()
    d = load()
    if args.review:
        for dish in DISHES:
            cand = candidates(d, dish)
            pick = f"   PICK {PICKS[dish]}" if dish in PICKS else ""
            print(f"\n{dish} ({len(cand)}){pick}")
            for _, r in cand.head(args.top).iterrows():
                print(f"  {r.score:6.1f} {r.recipe_id:>7} {r.name_n[:55]:55s} {r.total:>5.0f}m {r.n_steps:>3}st "
                      f"{r.n_photos:>3}ph")
        return
    out = build(d)
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} dishes; no recipe: {', '.join(sorted(NO_RECIPE))}")


if __name__ == "__main__":
    sys.exit(main())

"""One-off data fix (run once on 9 Nov 2026: python scrapers/fix_guessed_dish_labels.py --write): the Foodpanda sitemap scraper guessed 'lok lak' (ឡុកឡាក់) into the labels of every place whose
NAME had 'rice', 'curry', 'ptes bay', 'bay bak'... (no menu or listing said so); the label was copied into dish_en,
dish_kh, description, and normalize_and_merge.py tagged those places lok_lak. Remove the guessed lok lak unless the
place's name or menu shows it."""
import re, sys
import pandas as pd
REPLACE = [("បាយកុម្ម៉ង់ ឡុកឡាក់ និងម្ហូបខ្មែរ", "បាយកុម្ម៉ង់ និងម្ហូបខ្មែរ"),     # made-to-order rice dishes and Khmer food
           ("បាយសាច់ជ្រូក ឡុកឡាក់ និងម្ហូបខ្មែរ", "ម្ហូបបាយ និងម្ហូបខ្មែរ"),        # rice dishes and Khmer food
           (re.compile(r"(rice dishes) & lok lak", re.I), r"\1 & daily specials")]        # the scraper's English now
LOK = re.compile(r"lok ?lak|ឡុកឡាក់", re.I)


def fix(d):
    """-> (places changed, places that still mention lok lak with no evidence)"""
    guessed = ~(d["name"].str.contains(LOK) | d["menu"].str.contains(LOK))
    changed = pd.Series(False, index=d.index)
    for col in ("dish_kh", "dish_en", "description"):
        before = d[col].copy()
        for old, new in REPLACE:
            d.loc[guessed, col] = d.loc[guessed, col].str.replace(old, new, regex=not isinstance(old, str))
        changed |= d[col].ne(before)
    d.loc[changed, "tags"] = d.loc[changed, "tags"].map(
        lambda t: ";".join(x for x in t.split(";") if x and x not in ("lok_lak", "ឡុកឡាក់")))
    left = guessed & d.drop(columns=["name", "menu"]).apply(lambda c: c.str.contains(LOK)).any(axis=1)
    return int(changed.sum()), int(left.sum())


if __name__ == "__main__" and sys.argv[1:] == ["--write"]:
    path = "data/restaurants.csv"
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    print("changed %d places, still guessed: %d" % fix(d))
    d.to_csv(path, index=False)

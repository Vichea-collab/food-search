"""
Build the evaluation set for food_search.ipynb (section 2): data/eval/queries.csv + data/eval/judgments.csv.

How the labels are made (pooling + written rules, so no search method judges itself):
  1. POOL: for every test question, the top POOL_DEPTH places of each of the three methods (BM25, embeddings,
     hybrid) are collected. Only pooled places are judged (the usual practice in IR evaluation, e.g. TREC).
  2. JUDGE: each question has a written rule (QUESTIONS below): which words make a place "that dish" (searched in
     the place's name, category, tags and menu dishes, not in any score), and where it must be (khan / city, or
     within NEAR_KM of a landmark). A pooled place that meets the rule is relevant.
  3. CHECK: every judgment is written to data/eval/judgments.csv with the reason. Look through it and change a
     label (1 = relevant, 0 = not) where the rule got it wrong, then run this script with --from-judgments to
     rebuild queries.csv from your labels.
  Running it again ADDS to the pool (places a changed search now finds are judged too; earlier ones stay), so an old
  and a new version of the search can be compared on the same labels. A label you changed by hand (label differs
  from rule_label) is never overwritten. --rejudge starts again from the rules.

Usage:
    venv/bin/python scrapers/eval_build.py                  # pool, judge with the rules, write both files
    venv/bin/python scrapers/eval_build.py --from-judgments # rebuild queries.csv from an edited judgments.csv
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "data" / "eval"
POOL_DEPTH = 20
NEAR_KM = 3.0

# question, kind, words that make a place "that dish" (any of them), optional landmark for "near"
# (a khan / city in the question is read by the app's own parser and must match the place's area / city)
QUESTIONS = [
    # dishes, English
    ("kuy teav", "dish", ["kuy teav", "kuyteav", "kuy tiew", "kuytiew", "គុយទាវ", "noodle soup", "rice noodle"]),
    ("lok lak", "dish", ["lok lak", "loklak", "ឡុកឡាក់"]),
    ("amok", "dish", ["amok", "អាម៉ុក"]),
    ("bai sach chrouk", "dish", ["bai sach chrouk", "bay sach chrouk", "bai sach", "bay sach", "បាយសាច់ជ្រូក", "pork rice", "rice with pork"]),
    ("num banh chok", "dish", ["num banh chok", "nom banh chok", "nom banhchok", "numbanhchok", "banh chok", "banh chuk", "នំបញ្ចុក"]),
    ("pizza", "dish", ["pizza", "ភីហ្សា"]),
    ("sushi", "dish", ["sushi", "ស៊ូស៊ី"]),
    ("burger", "dish", ["burger", "ប៊ឺហ្គឺ"]),
    ("fried rice", "dish", ["fried rice", "បាយឆា"]),
    ("bubble tea", "dish", ["bubble tea", "milk tea", "boba", "pearl tea", "តែគុជ", "តែទឹកដោះគោ"]),
    ("khmer bbq", "dish", ["bbq", "barbecue", "grill", "សាច់អាំង", "អាំង"]),
    ("coffee", "dish", ["coffee", "cafe", "café", "espresso", "កាហ្វេ"]),
    # dishes, Khmer
    ("គុយទាវ", "dish_kh", ["kuy teav", "kuyteav", "kuy tiew", "គុយទាវ", "noodle soup", "rice noodle"]),
    ("ឡុកឡាក់", "dish_kh", ["lok lak", "loklak", "ឡុកឡាក់"]),
    ("បាយសាច់ជ្រូក", "dish_kh", ["bai sach chrouk", "bay sach chrouk", "bai sach", "bay sach", "បាយសាច់ជ្រូក", "pork rice"]),
    ("នំបញ្ចុក", "dish_kh", ["num banh chok", "nom banh chok", "nom banhchok", "banh chok", "banh chuk", "នំបញ្ចុក"]),
    ("កាហ្វេ", "dish_kh", ["coffee", "cafe", "café", "កាហ្វេ"]),
    ("ភីហ្សា", "dish_kh", ["pizza", "ភីហ្សា"]),
    ("តែគុជ", "dish_kh", ["bubble tea", "milk tea", "boba", "pearl tea", "តែគុជ"]),
    ("បាយឆា", "dish_kh", ["fried rice", "បាយឆា"]),
    # typos
    ("kuytiew", "typo", ["kuy teav", "kuyteav", "kuy tiew", "kuytiew", "គុយទាវ", "noodle soup"]),
    ("carry noodle", "typo", ["curry", "kari", "ការី"]),
    ("piza", "typo", ["pizza"]),
    ("cofee", "typo", ["coffee", "cafe", "café", "កាហ្វេ"]),
    ("sushii", "typo", ["sushi"]),
    ("num banh chuk", "typo", ["num banh chok", "nom banh chok", "banh chok", "banh chuk", "នំបញ្ចុក"]),
    # meaning only (the words are not in the question)
    ("something sweet", "meaning", ["dessert", "cake", "ice cream", "bakery", "pastry", "sweet", "waffle", "donut",
                                    "chocolate", "បង្អែម", "ការ៉េម", "នំ"]),
    ("vegetarian food", "meaning", ["vegetarian", "vegan", "plant-based", "បួស"]),
    ("spicy noodle soup", "meaning", ["spicy", "mi hel", "mihel", "tom yum", "tomyum", "ramen", "ហឹរ", "មីហិល"]),
    ("breakfast", "meaning", ["breakfast", "brunch", "bakery", "nom pang", "bor bor", "porridge", "បបរ", "អាហារពេលព្រឹក"]),
    ("seafood", "meaning", ["seafood", "crab", "shrimp", "prawn", "squid", "fish", "គ្រឿងសមុទ្រ", "ក្តាម", "បង្គា"]),
    ("hot pot", "meaning", ["hot pot", "hotpot", "shabu", "steamboat", "ស៊ុបឆ្នាំងភ្លើង", "ហតផត"]),
    # dish + khan / city
    ("coffee in Toul Kork", "area", ["coffee", "cafe", "café", "កាហ្វេ"]),
    ("pizza in BKK1", "area", ["pizza", "ភីហ្សា"]),
    ("kuy teav in Siem Reap", "area", ["kuy teav", "kuyteav", "kuy tiew", "គុយទាវ", "noodle soup", "noodle"]),
    ("bbq in Sen Sok", "area", ["bbq", "barbecue", "grill", "សាច់អាំង", "អាំង"]),
    ("sushi in Chamkar Mon", "area", ["sushi", "japanese", "ស៊ូស៊ី"]),
    ("កាហ្វេ នៅទួលគោក", "area", ["coffee", "cafe", "café", "កាហ្វេ"]),
    ("bubble tea in Daun Penh", "area", ["bubble tea", "milk tea", "boba", "pearl tea", "តែគុជ"]),
    ("noodles in Battambang", "area", ["noodle", "kuy teav", "mi ", "មី", "គុយទាវ", "នំបញ្ចុក", "banh chok"]),
    # dish + landmark ("near X": within NEAR_KM)
    ("coffee near CADT", "near", ["coffee", "cafe", "café", "កាហ្វេ"], "CADT"),
    ("kuy teav near Independence Monument", "near", ["kuy teav", "kuyteav", "kuy tiew", "គុយទាវ", "noodle soup"], "Independence Monument"),
    ("pizza near Aeon Mall 1", "near", ["pizza", "ភីហ្សា"], "Aeon Mall 1"),
    ("bbq near Russian Market", "near", ["bbq", "barbecue", "grill", "សាច់អាំង"], "Russian Market"),
    # a named place or chain (any branch)
    ("starbucks", "named", ["starbucks"]),
    ("pizza company", "named", ["pizza company", "ភីហ្សាខមភើនី"]),
    ("brown coffee", "named", ["brown"]),
    ("costa coffee", "named", ["costa"]),
    ("9k foods chhouk meas", "named", ["9k foods"]),
    ("khmer surin", "named", ["khmer surin"]),
]


def place_text(r) -> str:
    """What a place says about itself (no search scores): name, category, tags, menu dishes."""
    menu = ""
    if isinstance(r.get("menu"), str) and r["menu"].startswith("["):
        try:
            menu = " ".join(f"{m.get('name_en') or ''} {m.get('name_kh') or ''}" for m in json.loads(r["menu"]))
        except ValueError:
            pass
    return " ".join(str(r.get(c) or "") for c in ("name", "dish_en", "dish_kh", "tags")).replace(";", " ").lower() + " " + menu.lower()


def build(rejudge=False):
    old = pd.DataFrame()
    if (EVAL / "judgments.csv").exists() and not rejudge:
        old = pd.read_csv(EVAL / "judgments.csv")
        if "rule_label" not in old:
            old["rule_label"] = old["label"]
    sys.path.insert(0, str(ROOT / "backend"))
    from food_search import search as S
    S.init()
    df = S.df.set_index("id", drop=False)
    rows, judgments = [], []
    for spec in QUESTIONS:
        query, kind, words = spec[0], spec[1], [w.lower() for w in spec[2]]
        landmark = spec[3] if len(spec) > 3 else None
        _, flt = S.parse_query_filters(query)
        spot = S.geocode_place(landmark) if landmark else None
        before = old[old["query"] == query] if len(old) else pd.DataFrame()
        pool = list(before["id"]) if len(before) else []
        # the hybrid search as the app runs it: with the landmark found on the map ("near CADT" -> distances)
        for fn in (lambda q: S.bm25_search(q, POOL_DEPTH), lambda q: S.embedding_search(q, POOL_DEPTH),
                   lambda q: S.hybrid_search(q, POOL_DEPTH, user_loc=spot)):
            pool += [i for i in fn(query)["id"] if i not in pool]
        relevant = []
        for pid in pool:
            r = df.loc[pid]
            text = place_text(r)
            hit = next((w for w in words if w in text), None)
            where_ok, where = True, ""
            if flt.get("area"):
                where_ok = r["area_key"] == S.normalize_text(flt["area"])
                where = f"area {r['area']}"
            elif flt.get("city"):
                where_ok = r["city_key"] == S.normalize_text(flt["city"])
                where = f"city {r['city']}"
            elif spot:
                km = float(S.haversine_km(spot[0], spot[1], r["lat"], r["lng"])) if pd.notna(r["lat"]) else float("inf")
                where_ok = km <= NEAR_KM
                where = f"{km:.1f} km from {landmark}"
            rule_label = int(bool(hit) and where_ok)
            reason = (f"has '{hit}'" if hit else "dish words not in its name/category/tags/menu") + (f"; {where}" if where else "")
            label = rule_label
            prev = before[before["id"] == pid] if len(before) else pd.DataFrame()
            if len(prev) and int(prev["label"].iloc[0]) != int(prev["rule_label"].iloc[0]):
                label, reason = int(prev["label"].iloc[0]), "checked by hand"      # a person's label wins
            judgments.append({"query": query, "id": pid, "label": label, "rule_label": rule_label, "name": r["name"],
                              "dish": r["dish_en"], "area": r["area"], "reason": reason})
            if label:
                relevant.append(pid)
        rows.append({"query": query, "relevant_ids": ";".join(relevant), "lang": "kh" if S.detect_lang(query) == "kh" else "en",
                     "kind": kind, "pooled": len(pool), "relevant": len(relevant)})
        print(f"{query:38} {kind:8} pooled {len(pool):3d}  relevant {len(relevant):3d}")
    EVAL.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(judgments).to_csv(EVAL / "judgments.csv", index=False)
    write_queries(pd.DataFrame(rows))


def write_queries(rows):
    rows = rows[rows["relevant_ids"].str.len() > 0]                # a question with nothing relevant cannot be scored
    rows[["query", "relevant_ids", "lang", "kind"]].to_csv(EVAL / "queries.csv", index=False)
    print(f"\n{len(rows)} questions -> {EVAL.relative_to(ROOT)}/queries.csv "
          f"(judgments: {EVAL.relative_to(ROOT)}/judgments.csv)")


def from_judgments():
    j = pd.read_csv(EVAL / "judgments.csv")
    kinds = {q[0]: q[1] for q in QUESTIONS}
    sys.path.insert(0, str(ROOT / "backend"))
    from food_search.search import detect_lang
    rows = [{"query": q, "relevant_ids": ";".join(g.loc[g["label"] == 1, "id"]), "kind": kinds.get(q, ""),
             "lang": "kh" if detect_lang(q) == "kh" else "en"} for q, g in j.groupby("query", sort=False)]
    write_queries(pd.DataFrame(rows))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-judgments", action="store_true", help="rebuild queries.csv from an edited judgments.csv")
    ap.add_argument("--rejudge", action="store_true", help="judge every pooled place again with the rules")
    args = ap.parse_args()
    from_judgments() if args.from_judgments else build(args.rejudge)

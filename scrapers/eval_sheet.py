"""
Make the labelling sheets for human relevance judgments (so the evaluation does not rest on word rules alone).

For every question in data/eval/queries.csv the places to label are the top 5 of BM25, of the embeddings and of the full
hybrid search (the usual "pooling": a place no method ranks high is taken as not relevant). Rows are shuffled and carry no
rule label and no method name, so the labeller is not anchored by either.

Two labellers, A and B. 40 questions are labelled by both (to measure agreement, Cohen's kappa); the other questions are
split between them, so each person labels ~100 questions (~1,000 places, about 2-3 hours).

  venv/bin/python scrapers/eval_sheet.py            # writes data/eval/labelling/annotator_A.csv and annotator_B.csv
Each labeller fills the `label` column: 1 = relevant, 0 = not (see docs/labelling-guide.md), then
  venv/bin/python scrapers/eval_agree.py data/eval/labelling/annotator_A.csv data/eval/labelling/annotator_B.csv
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
OUT = ROOT / "data/eval/labelling"
COMMON = 40
SOURCES = {"overture", "foodpanda", "openstreetmap", "grab", "canby", "yellowpages", "foodchow"}


def main():
    from food_search import search as S
    S.init()
    df = S.df.set_index("id", drop=False)
    q = pd.read_csv(ROOT / "data/eval/queries.csv", dtype=str)
    rng = np.random.default_rng(42)
    lm = {}

    def landmark(text):
        near = S.parse_query_filters(text)[1].get("near")
        if not near or near == "me":
            return None
        if near not in lm:
            lm[near] = S.geocode_place(near)
        return lm[near]

    rows = []
    for text, kind in zip(q["query"], q["kind"]):
        spot = landmark(text)
        ids = []
        for fn in (lambda t: S.bm25_search(t, 5), lambda t: S.embedding_search(t, 5),
                   lambda t: S.hybrid_search(t, 5, user_loc=spot)):
            ids += [i for i in fn(text)["id"] if i not in ids]
        ids = list(rng.permutation(ids))
        for pid in ids:
            r = df.loc[pid]
            menu = ""
            if isinstance(r["menu"], str) and r["menu"].startswith("["):
                try:
                    menu = "; ".join((m.get("name_en") or m.get("name") or "") for m in json.loads(r["menu"])[:6])
                except ValueError:
                    pass
            tags = ", ".join(t for t in str(r["tags"]).split(";") if t and t not in SOURCES)[:90]
            km = ""
            if spot and pd.notna(r["lat"]):
                km = f"{float(S.haversine_km(spot[0], spot[1], r['lat'], r['lng'])):.1f}"
            rows.append({"query": text, "id": pid, "name": r["name"], "khan": r["area"], "category": r["dish_en"],
                         "tags": tags, "menu": menu, "km_from_landmark": km, "link": r["page_url"], "label": "", "notes": ""})
    sheet = pd.DataFrame(rows)
    queries = list(dict.fromkeys(sheet["query"]))
    order = list(rng.permutation(queries))
    common, rest = order[:COMMON], order[COMMON:]
    a_only, b_only = rest[0::2], rest[1::2]
    OUT.mkdir(parents=True, exist_ok=True)
    for name, own in (("A", a_only), ("B", b_only)):
        part = sheet[sheet["query"].isin(common + own)].copy()
        part["query"] = pd.Categorical(part["query"], categories=list(rng.permutation(common + own)), ordered=True)
        part = part.sort_values("query", kind="stable")
        part["shared"] = part["query"].astype(str).isin(common).map({True: "both", False: name})
        part.to_csv(OUT / f"annotator_{name}.csv", index=False)
        print(f"annotator_{name}.csv: {part['query'].nunique()} questions, {len(part)} places "
              f"({int((part['shared'] == 'both').sum())} shared with the other labeller)")


if __name__ == "__main__":
    main()

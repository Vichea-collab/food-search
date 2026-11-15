"""
Agreement between two labelling sheets and the human-labelled evaluation set.

  venv/bin/python scrapers/eval_agree.py annotator_A.csv annotator_B.csv

  * Cohen's kappa and percent agreement on the places both labelled (the questions marked `shared == both`),
  * the disagreements, written to data/eval/labelling/disagreements.csv for the two labellers to settle together
    (fill `final` with 1 or 0),
  * data/eval/human_judgments.csv: every place with its human label (shared places: the settled `final` when present,
    else the common label; unsettled disagreements are left out) and data/eval/queries_human.csv, the same format as
    queries.csv, which `scrapers/eval_run.py --queries data/eval/queries_human.csv` scores.
  * also kappa between the people and the word rules (`rule_label` in data/eval/judgments.csv).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "data/eval/labelling"


def kappa(a, b):
    a, b = np.asarray(a, int), np.asarray(b, int)
    po = (a == b).mean()
    pe = sum(((a == v).mean() * (b == v).mean()) for v in (0, 1))
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def load(path):
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    bad = d[~d["label"].isin(["0", "1"])]
    if len(bad):
        sys.exit(f"{path}: {len(bad)} places have no label 0/1 yet (first: {bad.iloc[0]['query']!r} / {bad.iloc[0]['name']!r})")
    d["label"] = d["label"].astype(int)
    return d


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    a, b = load(sys.argv[1]), load(sys.argv[2])
    both = a[a["shared"] == "both"].merge(b[b["shared"] == "both"][["query", "id", "label", "notes"]],
                                          on=["query", "id"], suffixes=("_A", "_B"))
    print(f"{len(both)} places labelled by both ({both['query'].nunique()} questions)")
    print(f"agreement {(both['label_A'] == both['label_B']).mean():.1%} | Cohen's kappa {kappa(both['label_A'], both['label_B']):.2f} "
          "(0.6-0.8 = substantial, above 0.8 = almost perfect)")
    dis = both[both["label_A"] != both["label_B"]][["query", "id", "name", "khan", "category", "tags", "menu", "label_A", "label_B", "notes_A", "notes_B"]].assign(final="")
    dis.to_csv(LAB / "disagreements.csv", index=False)
    print(f"{len(dis)} disagreements -> {LAB / 'disagreements.csv'} (settle them together, fill `final`)")
    final = {}
    p = LAB / "disagreements.csv"
    for _, r in pd.read_csv(p, dtype=str, keep_default_na=False).iterrows():
        if r["final"] in ("0", "1"):
            final[(r["query"], r["id"])] = int(r["final"])
    rows = []
    for _, r in both.iterrows():
        k = (r["query"], r["id"])
        lab = final.get(k, r["label_A"] if r["label_A"] == r["label_B"] else None)
        if lab is not None:
            rows.append({"query": r["query"], "id": r["id"], "label": lab})
    for d in (a, b):
        for _, r in d[d["shared"] != "both"].iterrows():
            rows.append({"query": r["query"], "id": r["id"], "label": r["label"]})
    j = pd.DataFrame(rows)
    j.to_csv(ROOT / "data/eval/human_judgments.csv", index=False)
    kinds = pd.read_csv(ROOT / "data/eval/queries.csv", dtype=str).set_index("query")[["lang", "kind"]]
    qh = (j[j["label"] == 1].groupby("query")["id"].apply(";".join).rename("relevant_ids").reset_index()
          .join(kinds, on="query"))[["query", "relevant_ids", "lang", "kind"]]
    qh.to_csv(ROOT / "data/eval/queries_human.csv", index=False)
    print(f"human labels: {len(j)} judgments, {len(qh)} questions with a relevant place -> data/eval/queries_human.csv")
    rules = pd.read_csv(ROOT / "data/eval/judgments.csv", dtype=str)[["query", "id", "rule_label"]]
    m = j.merge(rules, on=["query", "id"])
    if len(m):
        print(f"people vs word rules: agreement {(m['label'].astype(int) == m['rule_label'].astype(int)).mean():.1%}, "
              f"kappa {kappa(m['label'], m['rule_label']):.2f} ({len(m)} places)")


if __name__ == "__main__":
    main()

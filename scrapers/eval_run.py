"""
Run the retrieval evaluation outside the notebook: the same four methods, metrics and landmark handling as
food_search.ipynb section 5, plus a 95% bootstrap interval on every mean (47 questions are few: a single number
can look better or worse than it is).

  venv/bin/python scrapers/eval_run.py            # prints the tables, writes results/eval_results.csv,
                                                  # results/eval_by_kind.csv, results/eval_per_query.csv
  venv/bin/python scrapers/eval_run.py --rerank BAAI/bge-reranker-v2-m3   # adds a "Hybrid + reranker" row
  venv/bin/python scrapers/eval_run.py --rerank BAAI/bge-reranker-v2-m3 --fusion
                                                  # + multi-query, HyDE, both (RAG-Fusion), and the full live search
                                                  # (the AI's wordings are saved in data/eval/expansions.json, so a
                                                  # re-run gives the same numbers without AI calls)
  venv/bin/python scrapers/eval_run.py --queries data/eval/queries_human.csv --tag human
                                                  # the human-labelled set: writes results/eval_results_human.csv ...
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from food_search import search as S  # noqa: E402

K = 5


def precision(ranked, rel): return len(set(ranked[:K]) & rel) / K
def recall(ranked, rel): return len(set(ranked[:K]) & rel) / len(rel) if rel else 0.0
def mrr(ranked, rel): return next((1 / r for r, d in enumerate(ranked[:K], 1) if d in rel), 0.0)


def ndcg(ranked, rel):
    dcg = sum(1 / math.log2(r + 1) for r, d in enumerate(ranked[:K], 1) if d in rel)
    ideal = sum(1 / math.log2(r + 1) for r in range(1, min(len(rel), K) + 1))
    return dcg / ideal if ideal else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", default=str(ROOT / "data/eval/queries.csv"))
    ap.add_argument("--tag", default="", help="suffix for the result files, e.g. human -> eval_results_human.csv")
    ap.add_argument("--rerank", default="", help="also score the hybrid with this cross-encoder, e.g. BAAI/bge-reranker-v2-m3")
    ap.add_argument("--fusion", action="store_true", help="also score multi-query, HyDE and both (needs the AI once)")
    ap.add_argument("--expansions", default=str(ROOT / "data/eval/expansions.json"))
    args = ap.parse_args()
    sfx = f"_{args.tag}" if args.tag else ""
    S.init()
    S.RERANK_MODEL = ""          # RERANK_MODEL in .env switches the reranker on for the app: the baselines must not use it
    q = pd.read_csv(args.queries, dtype={"relevant_ids": str})
    q["relevant"] = q["relevant_ids"].fillna("").str.split(";").map(lambda x: {i for i in x if i})
    known = set(S.df["id"])
    q = q[q["relevant"].map(lambda r: bool(r & known))].reset_index(drop=True)
    lm = {}

    def landmark(text):
        near = S.parse_query_filters(text)[1].get("near")
        if not near or near == "me":
            return None
        if near not in lm:
            lm[near] = S.geocode_place(near)
        return lm[near]

    methods = {
        "BM25 + fuzzy": lambda t: S.bm25_search(t, K)["id"].tolist(),
        "Embeddings": lambda t: S.embedding_search(t, K)["id"].tolist(),
        "Hybrid (no filters)": lambda t: S.hybrid_search(t, K, use_query_filters=False)["id"].tolist(),
        "Hybrid": lambda t: S.hybrid_search(t, K, user_loc=landmark(t))["id"].tolist(),
    }
    if args.rerank:
        def reranked(t):
            S.RERANK_MODEL = args.rerank
            try:
                return S.hybrid_search(t, K, user_loc=landmark(t))["id"].tolist()
            finally:
                S.RERANK_MODEL = ""
        methods["Hybrid + reranker"] = reranked
    if args.fusion:
        from food_search import llm as L
        path = Path(args.expansions)
        saved = json.loads(path.read_text()) if path.exists() else {}
        for text in q["query"]:
            if text not in saved:
                L.EXPANSIONS.pop(L.expansion_key(text), None)
                saved[text] = L.expand_search(text) or {"variants": [], "hyde": ""}
                path.write_text(json.dumps(saved, ensure_ascii=False, indent=1))
        print(f"wordings: {sum(bool(v.get('variants')) for v in saved.values())} of {len(q)} questions")

        def fused(t, use_variants, use_hyde, rerank=False, retry=False):
            exp = saved.get(t) or {}
            variants = exp.get("variants") if use_variants else None
            hyde = exp.get("hyde") if use_hyde else None
            S.RERANK_MODEL = args.rerank if rerank else ""
            try:
                fn = S.search_with_retry if retry else S.hybrid_search
                return fn(t, K, landmark(t), variants=variants, hyde=hyde)["id"].tolist()
            finally:
                S.RERANK_MODEL = ""
        methods["Hybrid + multi-query"] = lambda t: fused(t, True, False)
        methods["Hybrid + HyDE"] = lambda t: fused(t, False, True)
        methods["Hybrid + multi-query + HyDE"] = lambda t: fused(t, True, True)
        if args.rerank:
            methods["Hybrid + reranker + multi-query"] = lambda t: fused(t, True, False, True)
            methods["Hybrid + reranker + HyDE"] = lambda t: fused(t, False, True, True)
            methods["Hybrid + reranker + multi-query + HyDE"] = lambda t: fused(t, True, True, True)
            methods["Live search (all + retry)"] = lambda t: fused(t, True, True, True, True)
    rows = []
    for name, fn in methods.items():
        for text, rel, kind in zip(q["query"], q["relevant"], q["kind"]):
            ranked = fn(text)
            rows.append(dict(method=name, query=text, kind=kind, n_relevant=len(rel), **{
                "P@5": precision(ranked, rel), "Recall@5": recall(ranked, rel), "MRR": mrr(ranked, rel), "nDCG@5": ndcg(ranked, rel)}))
    per = pd.DataFrame(rows)
    metrics = ["P@5", "Recall@5", "MRR", "nDCG@5"]
    rng = np.random.default_rng(0)
    out = {}
    for name, g in per.groupby("method", sort=False):
        res = {}
        for m in metrics:
            v = g[m].to_numpy()
            boots = [rng.choice(v, len(v)).mean() for _ in range(2000)]
            res[m] = round(v.mean(), 3)
            res[m + " 95% CI"] = f"{np.percentile(boots, 2.5):.2f}-{np.percentile(boots, 97.5):.2f}"
        out[name] = res
    table = pd.DataFrame(out).T
    (ROOT / "results").mkdir(exist_ok=True)
    table[metrics].to_csv(ROOT / f"results/eval_results{sfx}.csv")
    table.to_csv(ROOT / f"results/eval_results_ci{sfx}.csv")
    by_kind = per.pivot_table(index="kind", columns="method", values=["P@5", "nDCG@5"], aggfunc="mean").round(2)
    by_kind.insert(0, "questions", per[per.method == "Hybrid"].groupby("kind").size())
    by_kind.to_csv(ROOT / f"results/eval_by_kind{sfx}.csv")
    per.to_csv(ROOT / f"results/eval_per_query{sfx}.csv", index=False)
    print(f"{len(q)} questions, {len(S.df)} places\n")
    print(table.to_string()); print("\n", by_kind.to_string())


if __name__ == "__main__":
    main()

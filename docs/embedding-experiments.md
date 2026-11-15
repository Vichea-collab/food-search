# Embedding model and fusion experiments (13 Nov 2026)

**Question.** The current embeddings (`paraphrase-multilingual-MiniLM-L12-v2`) do not list Khmer among their training
languages and score 0.10 P@5 on Khmer dish queries when used alone. Would a Khmer-capable model (XLM-R based), or a
different way to mix BM25 and embeddings, improve the hybrid search?

**Setup.** 47 questions, 14,842 places, labels from `scrapers/eval_build.py` (strong evidence: dish in the name or on a
real menu), full hybrid search as the app runs it (filters, landmark distance). Metric: nDCG@5 (P@5 and MRR agree).
Models: `intfloat/multilingual-e5-base` (768-d), `BAAI/bge-m3` (1024-d), documents cut at 256 tokens. Each model's
"no keyword hit, so close in meaning" threshold was recalibrated so the same share of places (15.7%) passes as with
MiniLM at 0.45. 47 questions are few: the 95% interval on a mean is about +-0.07, so differences under ~0.05 mean nothing.

| Embedding in the hybrid | query sent to the embedder | best weight | nDCG@5 | MRR | P@5 |
|---|---|---|---|---|---|
| **MiniLM (current)** | expanded (synonym bag) | 0.5-0.65 | **0.90-0.91** | 0.95 | 0.87-0.89 |
| MiniLM | plain corrected text | 0.65 | 0.81 | 0.91 | 0.77 |
| multilingual-e5-base | expanded | 0.5 | 0.79 | 0.90 | 0.75 |
| multilingual-e5-base | plain | 0.65 | 0.80 | 0.92 | 0.76 |
| bge-m3 | expanded | 0.35 | 0.78 | 0.89 | 0.74 |
| bge-m3 | plain | 0.5 | 0.82 | 0.93 | 0.78 |
| MiniLM (expanded) + bge-m3 (plain), averaged | both | 0.65 | 0.91 | 0.97 | 0.87 |
| MiniLM, reciprocal-rank fusion instead of min-max | expanded | 0.5 | 0.78 | 0.90 | 0.73 |

Embeddings alone (no BM25), nDCG@5: MiniLM 0.49, e5-base 0.50 (plain), bge-m3 0.51 (plain).

**Findings.**
1. **No embedding or fusion change adopted.** No model or fusion tried beats the current MiniLM + min-max hybrid, and a
   MiniLM + bge-m3 ensemble only ties it (0.91) at three times the cost. The one idea that does help is a reranker
   (section below).
2. **The query expansion does the Khmer work.** `expand_query` adds Khmer and English synonyms ("kuy teav" -> គុយទាវ,
   noodle, ramen...). For MiniLM this is worth about +0.10 nDCG, because MiniLM cannot read the Khmer itself.
   The Khmer-capable models do better *without* the expansion (it makes them return udon and ramen shops).
3. **Dense scores must be cut to the top N.** The app keeps only the `EMBED_CANDIDATES` best places from the index and
   scores the rest 0. Min-max over all 14,842 places of a model whose cosines sit in a narrow band (e5: 0.77-0.88)
   turns noise into signal and cost 0.15-0.25 nDCG in a first, unfair run.
4. **Reciprocal-rank fusion is worse here (-0.12).** A BM25 match on the dish in a place's name and a weak match
   share rank 1 and rank 30; the min-max blend keeps that margin, RRF throws it away.
5. Standalone, e5 and bge-m3 are only on par with MiniLM (0.50 vs 0.49 nDCG@5), so the Khmer-coverage gap is not what
   limits the current system; the labels reward name/menu evidence, which BM25 supplies.

**Not tried.** Fine-tuning an embedder on Khmer food data (would need labelled pairs); a cross-encoder reranker over
the top 30 (next best idea); a larger question set (the limit on what can be measured).

## Cross-encoder reranker (adopted as an opt-in feature, 15 Nov 2026)

A cross-encoder reads the question and one place *together* instead of comparing two separate vectors.
`BAAI/bge-reranker-v2-m3` (XLM-R based, reads Khmer, 2.2 GB) re-orders the hybrid's best places. Scored on the 160
questions of `data/eval/queries.csv` (word-rule labels), 14,561 places:

| | P@5 | MRR | nDCG@5 (95% CI) |
|---|---|---|---|
| Hybrid (current) | 0.859 | 0.930 | 0.885 (0.85-0.92) |
| + reranker on the top 10 | 0.896 | 0.961 | **0.927** (0.90-0.96) |
| + reranker on the top 20 / top 30 | 0.891 | 0.954 / 0.953 | 0.922 / 0.923 |
| blended with the hybrid score (weight 0.3 / 0.6, top 10) | 0.875 / 0.890 | 0.948 / 0.966 | 0.904 / 0.923 |
| **as shipped** (top 10, not for "near" questions) | 0.891 | 0.961 | **0.923** (0.89-0.95) |

Paired bootstrap of the per-question difference: +0.042, 95% interval [+0.022, +0.064], so it is not luck. By kind
(nDCG@5, hybrid -> reranked): meaning 0.79 -> 0.87, area 0.91 -> 0.98, dish 0.87 -> 0.91, typo 0.80 -> 0.85,
dish_kh 0.91 -> 0.92, named 0.98 -> 0.98. Cost: about 0.2 s per question for the top 10 (0.7 s for 30) on an M3 Pro, and
2.2 GB of memory. Top 10 is as good as top 30, so it is the default.

**Why not for "near" questions.** It scored 1.00 against 0.93 there, but "near me" promises the closest place first and a
relevance order breaks that promise (`test_near_me_with_location_sorts_by_distance` failed with the reranker on).
So `hybrid_search` leaves distance-ordered results alone.

**Caveats.** (1) The labels are word rules (name or real menu), and the reranker reads the same name, category, tags and
menu text, so part of the gain may be agreement with the rules; the human labels (`docs/labelling-guide.md`) are the real
test, run `scrapers/eval_run.py --queries data/eval/queries_human.csv --tag human --rerank BAAI/bge-reranker-v2-m3`.
(2) Top-N and the blend weight were compared on the same questions; the options differ by less than 0.01, so this is
not a tuned knob. (3) The feature is OFF by default: set `RERANK_MODEL=BAAI/bge-reranker-v2-m3` in `.env` and restart
(the first search downloads and loads the model). If the model cannot load, search silently keeps the hybrid order.


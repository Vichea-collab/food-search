import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";
import type { CompareResponse, RankedRow } from "../../lib/types";
import { Meter } from "./Meter";

const EXAMPLES = ["curry noodle", "carry nodle", "something sweet and cold", "ភីហ្សា", "coffee open late"];

/** One ranked list. scaleMax: a fixed scale for scores that have one (cosine 0–1); none = relative to the best row. */
function RankedList({ title, sub, rows, inHybrid, digits, scaleMax }: {
  title: string; sub: string; rows: RankedRow[]; inHybrid: Set<string>; digits: number; scaleMax?: number;
}) {
  const top = scaleMax ?? Math.max(...rows.map((r) => r.score), 1e-9);
  return (
    <section className="demo-card">
      <h2 className="demo-card-title">{title}</h2>
      <p className="demo-card-sub">{sub}</p>
      {rows.length === 0 ? (
        <p className="demo-empty">Nothing to rank: the query has no search words.</p>
      ) : (
        <ol className="demo-ranked">
          {rows.map((r, i) => (
            <li key={r.id}>
              <span className="demo-rank">{i + 1}</span>
              <div className="demo-ranked-main">
                <span className="demo-pname">{r.name}</span>
                <span className="demo-psub">{[r.dish, r.area].filter(Boolean).join(", ")}</span>
                <div className="demo-ranked-score">
                  <Meter value={r.score} max={top} label={r.score.toFixed(digits)} />
                  {inHybrid.has(r.id) && <span className="demo-also">✓ in hybrid</span>}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

/** BM25 vs embeddings vs hybrid for the same query: shows why the app combines keywords and meaning. */
export function CompareTab() {
  const [query, setQuery] = useState("");
  const [weight, setWeight] = useState(0.5);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (q = query, w = weight) => {
    if (!q.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.demoCompare(q, w));
    } catch (e) {
      setError(e instanceof ApiError && e.kind === "client" && e.message !== "client" ? e.message
        : "Couldn't compare right now. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    void run();
  };

  const inHybrid = new Set(result?.in_hybrid ?? []);
  return (
    <div className="demo-compare">
      <form className="demo-compare-form" onSubmit={submit}>
        <div className="demo-field grow">
          <label htmlFor="cmpQuery">Query</label>
          <input id="cmpQuery" type="text" maxLength={200} autoComplete="off" value={query}
                 placeholder="e.g. curry noodle, or with a typo: carry nodle" onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="demo-field">
          <label htmlFor="cmpWeight">Hybrid weight <output htmlFor="cmpWeight">{weight.toFixed(2)}</output></label>
          <input id="cmpWeight" type="range" min={0} max={1} step={0.05} value={weight}
                 onChange={(e) => setWeight(Number(e.target.value))}
                 onPointerUp={() => result && void run(query, weight)}
                 onKeyUp={() => result && void run(query, weight)} />
          <span className="demo-field-hint">0 = BM25 only, 1 = embeddings only</span>
        </div>
        <button type="submit" className="demo-btn primary" disabled={busy || !query.trim()}>
          {busy ? "Comparing…" : "Compare"}
        </button>
      </form>

      <p className="demo-try-label">Try</p>
      <div className="demo-pills">
        {EXAMPLES.map((q) => (
          <button key={q} type="button" disabled={busy} onClick={() => { setQuery(q); void run(q, weight); }}>{q}</button>
        ))}
      </div>
      <p className="demo-hint">
        Try the typo “carry nodle”: keywords still find curry and noodles, while meaning alone drifts. That is why the app
        combines both.
      </p>

      {error && <p className="demo-error" role="alert">{error}</p>}
      {result && (
        <>
          <div className="demo-summary">
            <p>
              Search text <code>{result.text || "(none)"}</code>
              {result.filters.length > 0 && <> · conditions: {result.filters.join(", ")}</>} · keyword method:{" "}
              <b>{result.method}</b>
            </p>
            {result.text && (
              <p>
                BM25 and embeddings share <b>{result.shared} of their top {result.top_k}</b>. Hybrid keeps{" "}
                <b>{result.hybrid_from_bm25}</b> from BM25 and <b>{result.hybrid_from_embeddings}</b> from embeddings.
              </p>
            )}
          </div>
          <div className="demo-compare-grid">
            <RankedList title="BM25" sub="Keyword match, with typo fixing (bars relative to the best match)"
                        rows={result.bm25} inHybrid={inHybrid} digits={1} />
            <RankedList title="Embeddings" sub="Meaning (multilingual MiniLM), cosine similarity 0–1"
                        rows={result.embeddings} inHybrid={inHybrid} digits={2} scaleMax={1} />
            <RankedList title="Hybrid (what the app uses)"
                        sub={`${result.weight.toFixed(2)} × embedding + ${(1 - result.weight).toFixed(2)} × BM25, after filters`}
                        rows={result.hybrid} inHybrid={inHybrid} digits={2} scaleMax={1} />
          </div>
        </>
      )}
    </div>
  );
}

import type { ReactNode } from "react";
import type { DemoAskResponse } from "../../lib/types";

const TITLES = ["Understand the question", "Retrieve places", "Generate the answer"];

/** The 3 steps of an answer as a timeline. Before a question, each step explains what it does. */
export function Pipeline({ result, total, topK }: { result: DemoAskResponse | null; total: number | null; topK: number }) {
  let bodies: ReactNode[];
  if (!result) {
    bodies = [
      <p className="demo-muted">Finds the search words and conditions such as open now, an area or near CADT.</p>,
      <p className="demo-muted">
        BM25 keywords and multilingual embeddings rank {total ? `all ${total.toLocaleString()}` : "all the"} places; the
        best {topK} go to the model.
      </p>,
      <p className="demo-muted">The AI model writes one or two sentences using only those {topK} rows.</p>,
    ];
  } else {
    const s = result.steps;
    bodies = [
      <>
        <p>Search text <code>{s.text || "(only conditions)"}</code></p>
        <p>
          Conditions{" "}
          {s.filters.length ? s.filters.map((f) => <span key={f} className="demo-chip">{f}</span>) : <span className="demo-muted">none</span>}
        </p>
        <p className="demo-muted">Language: {s.lang === "kh" ? "Khmer" : "English"}</p>
      </>,
      <>
        <p><b>{s.matched.toLocaleString()}</b> of {s.total.toLocaleString()} places match; the top {s.top_k} go to the model.</p>
        <p className="demo-muted">
          Keyword method: {s.method} · {s.retrieve_ms.toLocaleString()} ms
          {s.geocoded && " (includes looking the place up on the map)"}
        </p>
      </>,
      result.provider === "gemini" || result.provider === "ollama" ? (
        <>
          <p>Written by <b>{result.model_label}</b> from those {s.top_k} rows only.</p>
          {result.fallback && (
            <p className="demo-muted">{result.chosen_label} did not answer (busy or over quota), so the next model in the list did.</p>
          )}
          <p className="demo-muted">
            Prompt: {s.prompt_chars.toLocaleString()} characters (≈{Math.floor(s.prompt_chars / 4).toLocaleString()} tokens) ·{" "}
            {s.generate_ms.toLocaleString()} ms
          </p>
        </>
      ) : result.provider === "no-results" ? (
        <p>Nothing was retrieved, so no model was called.</p>
      ) : (
        <>
          <p>Answered with <b>no AI model</b> (plain result cards).</p>
          <p className="demo-muted">No model was chosen, or every model in the list was busy, so the app shows the retrieved rows.</p>
        </>
      ),
    ];
  }

  return (
    <section className="demo-card" aria-label="Pipeline">
      <h2 className="demo-card-title">{result ? "How this answer was made" : "How an answer is made"}</h2>
      <ol className="demo-timeline">
        {TITLES.map((title, i) => (
          <li key={title} className={`demo-tl${result ? " done" : ""}`}>
            <span className="demo-tl-dot" aria-hidden="true">{i + 1}</span>
            <div className="demo-tl-body">
              <h3>{title}</h3>
              {bodies[i]}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

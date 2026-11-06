import { distanceText } from "../../lib/format";
import type { ScoredRow } from "../../lib/types";
import { Meter } from "./Meter";

/** The rows the model receives, with every score that ranked them. */
export function RowsTable({ rows, weight, asked }: { rows: ScoredRow[]; weight: number; asked: boolean }) {
  const top = Math.max(...rows.map((r) => r.final), 1e-9);
  return (
    <section className="demo-card" aria-label="Rows given to the model">
      <h2 className="demo-card-title">Rows given to the model</h2>
      <p className="demo-card-sub">
        final = {weight} × embedding + {+(1 - weight).toFixed(2)} × BM25 + small rating and distance bonuses (scores
        scaled 0–1 per query)
      </p>
      <div className="demo-table-wrap">
        <table className="demo-rows">
          <thead>
            <tr><th>#</th><th>Place</th><th>BM25</th><th>Embedding</th><th>Final</th><th>Distance</th></tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="demo-empty">
                  {asked ? "Nothing matched." : "The places the model reads will appear here."}
                </td>
              </tr>
            ) : (
              rows.map((r, i) => (
                <tr key={`${r.name}-${i}`}>
                  <td className="demo-rank">{i + 1}</td>
                  <td>
                    <span className="demo-pname">{r.name}</span>
                    <span className="demo-psub">{[r.dish, r.area].filter(Boolean).join(", ")}</span>
                  </td>
                  <td><Meter value={r.bm25} /></td>
                  <td><Meter value={r.embed} /></td>
                  <td><Meter value={r.final} max={top} /></td>
                  <td className="demo-km">{r.distance_km != null ? distanceText(r.distance_km) : ""}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

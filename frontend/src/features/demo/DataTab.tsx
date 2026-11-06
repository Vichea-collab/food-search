import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { DataStats } from "../../lib/types";

const SOURCE_NAMES: Record<string, string> = { openstreetmap: "OpenStreetMap", overture: "Overture Maps (Meta)" };

/** A single-series horizontal bar chart. `total` set = bars are shares of the whole (coverage);
 *  otherwise bars are relative to the largest row. Hover (or focus) a row for exact numbers. */
function HBars({ rows, total, asShare }: { rows: { name: string; count: number }[]; total: number; asShare?: boolean }) {
  const scale = asShare ? total : Math.max(...rows.map((r) => r.count), 1);
  return (
    <ul className="demo-hbars">
      {rows.map((r) => {
        const share = r.count / total;
        const tip = asShare
          ? `${r.name}: ${r.count.toLocaleString()} of ${total.toLocaleString()} places (${Math.round(share * 100)}%)`
          : `${r.name}: ${r.count.toLocaleString()} places (${Math.round(share * 100)}% of all)`;
        return (
          <li key={r.name} className="demo-hbar" tabIndex={0} aria-label={tip}>
            <span className="demo-hbar-label">{r.name}</span>
            <span className="demo-hbar-track">
              <span className={`demo-hbar-fill${r.count === 0 ? " zero" : ""}`} style={{ width: `${(r.count / scale) * 100}%` }} />
            </span>
            <span className="demo-hbar-value">{asShare ? `${Math.round(share * 100)}%` : r.count.toLocaleString()}</span>
            <span className="demo-tip" aria-hidden="true">{tip}</span>
          </li>
        );
      })}
    </ul>
  );
}

/** What the place list contains: it decides what the bot can and cannot answer. */
export function DataTab() {
  const [data, setData] = useState<DataStats | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api.demoData().then(setData).catch(() => setFailed(true));
  }, []);

  if (failed) return <p className="demo-error" role="alert">Couldn't load the data summary. Reload the page to try again.</p>;
  if (!data) return <p className="demo-muted">Loading…</p>;

  const n = data.total;
  const pct = (v: number) => `${Math.round((v / n) * 100)}%`;
  const tiles = [
    ["Places", n.toLocaleString()],
    ["Areas", data.area_count.toLocaleString()],
    ["With opening hours", pct(data.with_hours)],
    ["With a dish name", pct(data.with_dish)],
  ];
  const coverage = data.coverage.map((c) => ({ name: c.field, count: c.count }));
  const sources = data.sources.map((s) => ({ name: SOURCE_NAMES[s.name] ?? s.name, count: s.count }));

  return (
    <div className="demo-data">
      <div className="demo-tiles">
        {tiles.map(([label, value]) => (
          <div key={label} className="demo-tile">
            <p className="demo-tile-label">{label}</p>
            <p className="demo-tile-value">{value}</p>
          </div>
        ))}
      </div>
      <div className="demo-data-grid">
        <section className="demo-card">
          <h2 className="demo-card-title">What each place record contains</h2>
          <p className="demo-card-sub">
            Share of the {n.toLocaleString()} places that have each field. It decides what the bot can answer: area and
            distance work for every place, opening hours for only a few, and price or rating not until they are collected.
          </p>
          <HBars rows={coverage} total={n} asShare />
        </section>
        <section className="demo-card">
          <h2 className="demo-card-title">Places per area</h2>
          <p className="demo-card-sub">Number of places in each Phnom Penh khan, city or province</p>
          <HBars rows={data.areas} total={n} />
        </section>
        <div className="demo-stack">
          <section className="demo-card">
            <h2 className="demo-card-title">Places by type</h2>
            <p className="demo-card-sub">From the map category</p>
            <HBars rows={data.kinds} total={n} />
          </section>
          <section className="demo-card">
            <h2 className="demo-card-title">Where the places come from</h2>
            <p className="demo-card-sub">Data source of each place</p>
            <HBars rows={sources} total={n} />
          </section>
        </div>
      </div>
      <details className="demo-prompt">
        <summary>The same numbers as a table</summary>
        <div className="demo-table-wrap">
          <table className="demo-rows">
            <thead><tr><th>Field</th><th>Places with it</th><th>Share</th></tr></thead>
            <tbody>
              {coverage.map((c) => (
                <tr key={c.name}><td>{c.name}</td><td>{c.count.toLocaleString()}</td><td>{((c.count / n) * 100).toFixed(1)}%</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <p className="demo-foot">
        Place data © OpenStreetMap contributors (ODbL) and Overture Maps Foundation (Meta, CDLA Permissive 2.0). Add test
        queries to <code>data/eval/queries.csv</code> to measure search quality in <code>food_search.ipynb</code>.
      </p>
    </div>
  );
}

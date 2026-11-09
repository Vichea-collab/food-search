import { useRef, useState, type DragEvent } from "react";
import { Icon } from "../../components/Icon";
import { Markdown } from "../../components/Markdown";
import { api, ApiError } from "../../lib/api";
import type { DemoPhotoResponse } from "../../lib/types";
import { Meter } from "./Meter";

const pct = (x: number | null | undefined) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);
const minutes = (n: number) => (n >= 60 ? `${Math.floor(n / 60)} h${n % 60 ? ` ${n % 60} min` : ""}` : `${n} min`);

/** Photo -> dish, step by step: what the model sees, its top 5 guesses, then how the dish is used (recipe, places).
 *  Beside it: the three models compared on the test set (food_classification.ipynb). */
export function PhotoTab() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [res, setRes] = useState<DemoPhotoResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const run = async (f: File) => {
    if (!f.type.startsWith("image/")) {
      setErr("That file is not a photo.");
      return;
    }
    if (preview) URL.revokeObjectURL(preview);
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setErr(null);
    setBusy(true);
    try {
      setRes(await api.demoPhoto(f));
    } catch (e) {
      setRes(null);
      setErr(e instanceof ApiError && e.kind === "client" && e.message !== "client" ? e.message
        : e instanceof ApiError && e.kind === "offline" ? "Couldn't reach the server. Check your connection and try again."
        : "Something went wrong on the server. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files?.[0];
    if (f) void run(f);
  };

  const inUse = (name: string) => !!res?.model && res.model.toLowerCase().startsWith(name.toLowerCase().split(" ")[0]);

  return (
    <div className="demo-ask demo-photo">
      <div className="demo-ask-chat">
        <div
          className={`photo-drop${drag ? " drag" : ""}${preview ? " has-photo" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
        >
          {preview ? (
            <img src={preview} alt={file?.name ?? "Your photo"} />
          ) : (
            <div className="photo-drop-empty">
              <span className="photo-drop-icon"><Icon name="camera" /></span>
              <p className="demo-thread-empty-title">Drop a food photo here</p>
              <p className="demo-muted">or choose one. It is classified, then deleted (never stored).</p>
            </div>
          )}
          {busy && <div className="photo-busy" aria-label="Classifying"><i /><i /><i /></div>}
        </div>
        <input ref={input} type="file" accept="image/*" hidden
               onChange={(e) => { const f = e.target.files?.[0]; if (f) void run(f); e.target.value = ""; }} />
        <button type="button" className="demo-btn primary photo-pick" disabled={busy} onClick={() => input.current?.click()}>
          <Icon name="camera" />
          {preview ? "Try another photo" : "Choose a photo"}
        </button>
        {err && <p className="demo-bubble error" role="alert">{err}</p>}
        {res && (
          <div className="demo-bubble photo-lead" aria-live="polite">
            <Markdown text={res.lead} />
            {res.learned && (
              <p className="demo-note">
                Answered from a user correction ({res.learned.by_you ? "yours" : "someone else's"}, fingerprint
                similarity {res.learned.similarity.toFixed(2)}), not from the model's own top guess.
              </p>
            )}
          </div>
        )}
      </div>

      <div className="demo-ask-side">
        <section className="demo-card">
          <h2 className="demo-card-title">1 · What the model sees</h2>
          <p className="demo-card-sub">
            {res ? `Your photo (${res.input.width}×${res.input.height} px) is resized and centre-cropped to ` +
                   `${res.input.size}×${res.input.size} px, then its colours are normalised (ImageNet mean and std).`
                 : "The photo is resized and centre-cropped to the size the model was trained on."}
          </p>
          {res ? (
            <div className="photo-steps">
              {preview && <figure><img src={preview} alt="" /><figcaption>your photo</figcaption></figure>}
              <span className="photo-arrow" aria-hidden="true">→</span>
              <figure><img src={res.input.crop} alt="The cropped photo the model sees" />
                <figcaption>{res.input.size}×{res.input.size} input</figcaption></figure>
            </div>
          ) : <p className="demo-muted">Choose a photo to see it.</p>}
        </section>

        <section className="demo-card">
          <h2 className="demo-card-title">2 · Classify: top 5 of {res?.classes ?? "all"} dishes</h2>
          <p className="demo-card-sub">
            {res ? `${res.model} · ${res.classify_ms.toFixed(0)} ms (softmax probabilities)`
                 : "The model gives every dish a probability; the 5 highest are shown."}
          </p>
          {res ? (
            <ol className="photo-top">
              {res.guesses.map((g, i) => (
                <li key={g.id} className={i === 0 ? "best" : undefined}>
                  <span className="photo-top-name">
                    {g.name}
                    {g.name_kh && <span className="photo-kh"> {g.name_kh}</span>}
                    {g.khmer && <span className="photo-tag">Khmer</span>}
                  </span>
                  <Meter value={g.confidence} label={pct(g.confidence)} />
                </li>
              ))}
            </ol>
          ) : <p className="demo-muted">—</p>}
        </section>

        <section className="demo-card">
          <h2 className="demo-card-title">3 · Use the dish</h2>
          <p className="demo-card-sub">
            {res ? <>The chat then offers its recipe and searches the places for “{res.search_query}” ({res.retrieve_ms.toFixed(0)} ms).</>
                 : "The recognised dish becomes a recipe answer and a place search."}
          </p>
          {res?.recipe && (
            <dl className="photo-recipe">
              <div><dt>Recipe</dt><dd>{res.recipe.title}</dd></div>
              <div><dt>Time</dt><dd>{minutes(res.recipe.total_minutes)} ({minutes(res.recipe.prep_minutes)} prep + {minutes(res.recipe.cook_minutes)} cook)</dd></div>
              <div><dt>Recipe size</dt><dd>{res.recipe.ingredients} ingredients · {res.recipe.steps} steps{res.recipe.servings ? ` · serves ${res.recipe.servings}` : ""}</dd></div>
            </dl>
          )}
          {res && res.places.length > 0 && (
            <ol className="photo-places">
              {res.places.map((p, i) => (
                <li key={i}>
                  <a href={p.maps_url} target="_blank" rel="noopener noreferrer">{p.name}</a>
                  <span className="demo-muted">{[p.dish, p.area].filter(Boolean).join(" · ")}</span>
                  {p.matched.length > 0 && (
                    <span className="photo-match">🍽 {p.matched.map((m) => m.name + (m.price_usd > 0 ? ` $${m.price_usd.toFixed(2)}` : "")).join(" · ")}</span>
                  )}
                </li>
              ))}
            </ol>
          )}
          {!res && <p className="demo-muted">—</p>}
        </section>

        <section className="demo-card">
          <h2 className="demo-card-title">The three models compared</h2>
          <p className="demo-card-sub">Test set: 25,250 Food-101 + 233 Khmer photos never seen in training (food_classification.ipynb).</p>
          <div className="photo-table-wrap">
            <table className="photo-table">
              <thead>
                <tr><th>Model</th><th>Top-1</th><th>Top-5</th><th>Khmer</th><th>ms / photo</th><th>Params</th></tr>
              </thead>
              <tbody>
                {(res?.models ?? []).map((m) => (
                  <tr key={m.model} className={inUse(m.model) ? "in-use" : undefined}>
                    <td>{m.model}{inUse(m.model) && <span className="photo-tag">in the app</span>}</td>
                    <td><Meter value={m.top1} label={pct(m.top1)} /></td>
                    <td>{pct(m.top5)}</td>
                    <td>{pct(m.khmer)}</td>
                    <td>{m.ms.toFixed(1)}</td>
                    <td>{m.params_m.toFixed(1)} M</td>
                  </tr>
                ))}
                {!res && <tr><td colSpan={6} className="demo-muted">Shown after the first photo.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

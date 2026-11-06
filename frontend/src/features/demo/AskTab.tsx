import { useEffect, useRef, useState, type FormEvent } from "react";
import { Avatar } from "../../components/Avatar";
import { Icon } from "../../components/Icon";
import { Markdown } from "../../components/Markdown";
import { api, ApiError } from "../../lib/api";
import type { AppConfig, DemoAskResponse } from "../../lib/types";
import { Pipeline } from "./Pipeline";
import { RowsTable } from "./RowsTable";

const EXAMPLES = ["kuy teav", "coffee open now", "pizza in Toul Kork", "bubble tea near Aeon Mall", "ម្ហូបខ្មែរ", "late night food"];
/** Where distances are measured from (the demo has no location of its own, so "near me" has none). */
function originNote(o: DemoAskResponse["origin"]): string | undefined {
  if (o?.kind === "place") return `Distances are from ${o.name}.`;
  if (o?.kind === "not_found") return `Couldn't find “${o.name}” on the map, so there are no distances.`;
  if (o?.kind === "no_location") return "This page has no location. Write the place instead, e.g. “coffee near CADT”.";
  return undefined;
}

type Turn =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "bot"; text: string; note?: string; error?: boolean };

let turnId = 0;

/** Chat on the left; how the last answer was made on the right (steps, scored rows, the exact prompt). */
export function AskTab({ config }: { config: AppConfig | null }) {
  const [model, setModel] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [last, setLast] = useState<DemoAskResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const thread = useRef<HTMLDivElement>(null);
  const topK = 5;

  useEffect(() => {
    thread.current?.scrollTo({ top: thread.current.scrollHeight });
  }, [turns, busy]);

  const ask = async (query: string) => {
    const q = query.trim().slice(0, 200);
    if (!q || busy) return;
    setText("");
    setTurns((t) => [...t, { id: ++turnId, role: "user", text: q }]);
    setBusy(true);
    try {
      const res = await api.demoAsk(q, model ?? config?.default_model ?? null);
      const note = originNote(res.origin);
      setTurns((t) => [...t, { id: ++turnId, role: "bot", text: res.answer, note }]);
      setLast(res);
    } catch (e) {
      const message = e instanceof ApiError && e.kind === "client" && e.message !== "client" ? e.message
        : e instanceof ApiError && e.kind === "offline" ? "Couldn't reach the server. Check your connection and try again."
        : "Something went wrong on the server. Try again.";
      setTurns((t) => [...t, { id: ++turnId, role: "bot", text: message, error: true }]);
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    void ask(text);
  };

  return (
    <div className="demo-ask">
      <div className="demo-ask-chat">
        <div className="demo-toolbar">
          <label htmlFor="demoModel">AI model</label>
          <div className="select-wrap">
            <select id="demoModel" value={model ?? config?.default_model ?? ""} onChange={(e) => setModel(e.target.value)}
                    disabled={!config}>
              {config?.models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
              {config && <option value={config.no_llm}>No AI model (plain result cards)</option>}
            </select>
          </div>
          <button type="button" className="demo-btn ghost" disabled={busy || turns.length === 0}
                  onClick={() => { setTurns([]); setLast(null); }}>
            New chat
          </button>
        </div>

        <div className="demo-thread" ref={thread} aria-live="polite">
          {turns.length === 0 ? (
            <div className="demo-thread-empty">
              <Avatar size="xl" />
              <p className="demo-thread-empty-title">Ask for a dish, a place or a time</p>
              <p className="demo-muted">Each answer's steps appear in the panel beside it.</p>
            </div>
          ) : (
            turns.map((turn) =>
              turn.role === "user" ? (
                <div key={turn.id} className="demo-turn user"><p className="demo-bubble">{turn.text}</p></div>
              ) : (
                <div key={turn.id} className="demo-turn bot">
                  <Avatar size="sm" />
                  <div>
                    <div className={`demo-bubble${turn.error ? " error" : ""}`}><Markdown text={turn.text} /></div>
                    {turn.note && <p className="demo-note">{turn.note}</p>}
                  </div>
                </div>
              ),
            )
          )}
          {busy && (
            <div className="demo-turn bot">
              <Avatar size="sm" />
              <div className="demo-bubble demo-typing" aria-label="Answering"><i /><i /><i /></div>
            </div>
          )}
        </div>

        <form className="demo-ask-form" onSubmit={submit}>
          <label className="sr-only" htmlFor="demoQuestion">Question</label>
          <input id="demoQuestion" type="text" maxLength={200} autoComplete="off" value={text}
                 placeholder="Ask for a dish or place" onChange={(e) => setText(e.target.value)} />
          <button type="submit" className="demo-send" aria-label="Send" disabled={busy || !text.trim()}>
            <Icon name="send" />
          </button>
        </form>
        <p className="demo-try-label">Try</p>
        <div className="demo-pills">
          {EXAMPLES.map((q) => (
            <button key={q} type="button" disabled={busy} onClick={() => void ask(q)}>{q}</button>
          ))}
        </div>
      </div>

      <div className="demo-ask-side">
        <Pipeline result={last} total={config?.places ?? null} topK={topK} />
        <RowsTable rows={last?.rows ?? []} weight={last?.weight ?? 0.5} asked={!!last} />
        <details className="demo-prompt">
          <summary>Exact prompt sent to the model</summary>
          <pre>{last?.prompt || "Ask a question to see the prompt."}</pre>
        </details>
      </div>
    </div>
  );
}

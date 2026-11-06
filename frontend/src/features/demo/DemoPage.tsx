import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Avatar } from "../../components/Avatar";
import { Icon, type IconName } from "../../components/Icon";
import { api } from "../../lib/api";
import type { AppConfig } from "../../lib/types";
import { useTheme } from "../../theme/ThemeContext";
import { AskTab } from "./AskTab";
import { CompareTab } from "./CompareTab";
import { DataTab } from "./DataTab";
import "./demo.css";

const TABS = [
  { id: "ask", label: "Ask (RAG)" },
  { id: "compare", label: "Compare retrieval" },
  { id: "data", label: "Data" },
] as const;
type TabId = (typeof TABS)[number]["id"];

/** "How it works": the same pipeline as the chat, with every step exposed (for presentations and the report). */
export function DemoPage() {
  const [params, setParams] = useSearchParams();
  const tab: TabId = TABS.some((t) => t.id === params.get("tab")) ? (params.get("tab") as TabId) : "ask";
  const [config, setConfig] = useState<AppConfig | null>(null);
  const { pref, cycle } = useTheme();
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    document.title = "Klean Nham – how it works";
    api.config().then(setConfig).catch(() => {});
    return () => { document.title = "Klean Nham – Cambodia food guide"; };
  }, []);

  const select = (id: TabId) => setParams(id === "ask" ? {} : { tab: id }, { replace: true });

  // arrow keys move between tabs (the usual keyboard pattern for tabs)
  const onTabKey = (e: KeyboardEvent, i: number) => {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    const next = (i + step + TABS.length) % TABS.length;
    select(TABS[next].id);
    tabRefs.current[next]?.focus();
  };

  const themeIcon: IconName = pref === "light" ? "sun" : pref === "dark" ? "moon" : "auto";
  return (
    <div className="demo">
      <header className="demo-head">
        <Avatar size="md" />
        <div className="demo-head-text">
          <p className="demo-name">Klean Nham (ឃ្លានញ៉ាំ)</p>
          <h1>How the answers are made</h1>
        </div>
        <div className="demo-head-actions">
          <button type="button" className="icon-btn" aria-label={`Theme: ${pref}. Change theme`} title={pref} onClick={cycle}>
            <Icon name={themeIcon} />
          </button>
          <Link to="/" className="demo-btn primary">
            <Icon name="chat" />
            Open the chat app
          </Link>
        </div>
        <p className="demo-lead">
          <b>Retrieve:</b> hybrid search (BM25 keywords + multilingual embeddings) finds places in our list.{" "}
          <b>Generate:</b> an AI model writes a short answer from those rows only, so it cannot invent a restaurant.
        </p>
      </header>

      <nav className="demo-tabs" role="tablist" aria-label="Demo sections">
        {TABS.map((t, i) => (
          <button
            key={t.id}
            ref={(el) => { tabRefs.current[i] = el; }}
            id={`tab-${t.id}`}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            tabIndex={tab === t.id ? 0 : -1}
            onClick={() => select(t.id)}
            onKeyDown={(e) => onTabKey(e, i)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {/* all panels stay mounted (hidden when not selected), so each keeps its state when you switch tabs */}
      {TABS.map((t) => (
        <section key={t.id} id={`panel-${t.id}`} role="tabpanel" aria-labelledby={`tab-${t.id}`} className="demo-panel"
                 hidden={tab !== t.id}>
          {t.id === "ask" && <AskTab config={config} />}
          {t.id === "compare" && <CompareTab />}
          {t.id === "data" && <DataTab />}
        </section>
      ))}
    </div>
  );
}

import type { ReactNode } from "react";
import { Avatar } from "../../components/Avatar";
import { Markdown } from "../../components/Markdown";
import { useI18n } from "../../i18n/I18nContext";
import { timeText } from "../../lib/format";
import type { ChatResponse } from "../../lib/types";
import { PlaceList } from "./PlaceCard";
import { RecipeCard } from "./RecipeCard";
import type { Message } from "./useChat";

function Time({ at }: { at: Date; model?: string | null }) {
  return (
    <p className="time">
      <time dateTime={at.toISOString()}>{timeText(at)}</time>
    </p>
  );
}

function BotRow({ children }: { children: ReactNode }) {
  return (
    <div className="msg bot">
      <Avatar size="sm" />
      <div className="msg-body">{children}</div>
    </div>
  );
}

function UserRow({ children }: { children: ReactNode }) {
  return (
    <div className="msg user">
      <div className="msg-body">{children}</div>
    </div>
  );
}

function AiBadge() {
  const { t } = useI18n();
  return (
    <div className="ai-badge">
      <span className="ai-sparkle" aria-hidden="true">✨</span>
      <span>{t("aiBadge")}</span>
    </div>
  );
}

/** The dish in a photo: what it is (and how sure), other guesses to tap, its recipe, and places that serve it. */
function DishReply({ data, at, onPickDish }: { data: ChatResponse; at: Date; onPickDish: (id: string, name: string) => void }) {
  const { t } = useI18n();
  const dish = data.dish!;
  const results = data.results ?? [];
  // other guesses: when the model is unsure, or when a second guess is still likely
  const others = dish.alternatives.filter((a) => !dish.sure || a.confidence >= 0.15);
  return (
    <BotRow>
      <div className="bubble answer dish-lead">
        <Markdown text={data.answer ?? dish.name} />
        {dish.model && <p className="dish-model">{t("dishBy", { m: dish.model })}</p>}
      </div>
      {others.length > 0 && (
        <>
          <p className="note">{t("dishOthers")}</p>
          <div className="suggest dish-others">
            {others.map((a) => (
              <button key={a.id} type="button" onClick={() => onPickDish(a.id, a.name)}>
                {a.name} <span className="pct">{Math.min(99, Math.round(a.confidence * 100))}%</span>
              </button>
            ))}
          </div>
        </>
      )}
      {data.recipe ? (
        <>
          <RecipeCard recipe={data.recipe} />
          <p className="note">{t("recipeAsk")}</p>
        </>
      ) : (
        <p className="note">{t("noRecipe", { dish: dish.name })}</p>
      )}
      {results.length > 0 ? (
        <>
          <p className="note dish-places">{t("dishPlaces", { dish: dish.name })}</p>
          <PlaceList places={results} />
        </>
      ) : (
        <p className="note">{t("dishNoPlaces", { dish: dish.name })}</p>
      )}
      <Time at={at} />
    </BotRow>
  );
}

/** An answer about a dish's recipe ("how long does it take?"), with the recipe card under it. */
function RecipeReply({ data, at }: { data: ChatResponse; at: Date }) {
  const byAi = data.provider === "gemini" || data.provider === "ollama";
  return (
    <BotRow>
      <div className="bubble answer">
        {byAi && <AiBadge />}
        <Markdown text={data.answer ?? ""} />
      </div>
      {data.recipe && <RecipeCard recipe={data.recipe} focus={data.focus} />}
      <Time at={at} model={byAi ? data.model_label : null} />
    </BotRow>
  );
}

function Reply({ data, at, onPickDish }: { data: ChatResponse; at: Date; onPickDish: (id: string, name: string) => void }) {
  const { t } = useI18n();
  if (data.kind === "dish" && data.dish) return <DishReply data={data} at={at} onPickDish={onPickDish} />;
  if (data.kind === "recipe") return <RecipeReply data={data} at={at} />;
  const results = data.results ?? [];
  const o = data.origin;
  const note =
    o?.kind === "me" ? t("fromMe")
    : o?.kind === "place" ? t("fromPlace", { name: o.name })
    : o?.kind === "no_location" ? t("noLocation")
    : o?.kind === "not_found" ? t("notFound", { name: o.name })
    : null;
  if (data.kind === "followup" || data.kind === "chat") {      // an answer about places already shown, or small talk
    const byAi = data.provider === "gemini" || data.provider === "ollama";
    const tabular = data.shape === "list" || data.shape === "table";        // the answer already holds the details
    return (
      <BotRow>
        <div className={`bubble answer${data.shape === "table" ? " wide" : ""}`}>
          {byAi && (
            <div className="ai-badge">
              <span className="ai-sparkle" aria-hidden="true">✨</span>
              <span>{t("aiBadge")}</span>
            </div>
          )}
          <Markdown text={data.answer ?? ""} />
        </div>
        {results.length > 0 && !tabular && <PlaceList places={results} numbers={data.numbers} />}
        <Time at={at} model={byAi ? data.model_label : null} />
      </BotRow>
    );
  }
  const byAi = data.provider === "gemini" || data.provider === "ollama";
  return (
    <BotRow>
      {data.search_query && <p className="note searched">{t("searchedFor", { q: data.search_query })}</p>}
      {data.answer ? (
        <div className="bubble answer">
          {byAi && (
            <div className="ai-badge">
              <span className="ai-sparkle" aria-hidden="true">✨</span>
              <span>{t("aiBadge")}</span>
            </div>
          )}
          <Markdown text={data.answer} />
        </div>
      ) : data.no_match ? (
        <div className="bubble">{data.no_match}</div>
      ) : results.length > 0 ? (
        <div className="bubble">{t(data.provider === "photo" ? "photoLead" : "cardsLead")}</div>
      ) : null}
      {note && <p className={`note${o?.kind === "not_found" ? " warn" : ""}`}>{note}</p>}
      {data.unverified_note && <p className="note">{data.unverified_note}</p>}
      {results.length > 0 && <PlaceList places={results} />}
      <Time at={at} model={byAi ? data.model_label : null} />
    </BotRow>
  );
}

export function MessageView({
  message: m,
  onSuggestion,
  onPickDish,
}: {
  message: Message;
  onSuggestion: (q: string) => void;
  onPickDish: (id: string, name: string) => void;
}) {
  const { t, list } = useI18n();
  switch (m.kind) {
    case "greeting":
      return (
        <BotRow>
          <div className="bubble">{t("greeting")}</div>
          <div className="suggest">
            {list("suggestions").map((q) => (
              <button key={q} type="button" onClick={() => onSuggestion(q)}>{q}</button>
            ))}
          </div>
          <Time at={m.at} />
        </BotRow>
      );
    case "user-text":
      return (
        <UserRow>
          <div className="bubble">{m.text}</div>
          <Time at={m.at} />
        </UserRow>
      );
    case "user-photo":
      return (
        <UserRow>
          <img className="bubble" src={m.url} alt="" />
          <Time at={m.at} />
        </UserRow>
      );
    case "pending":
      return (
        <BotRow>
          <div className="bubble typing" aria-hidden="true"><i /><i /><i /></div>
        </BotRow>
      );
    case "reply":
      return <Reply data={m.data} at={m.at} onPickDish={onPickDish} />;
    case "error": {
      const text = m.error.kind === "offline" ? t("offline") : m.error.kind === "client" && m.error.message !== "client"
        ? m.error.message : t("server");
      return (
        <BotRow>
          <div className="bubble">{text}</div>
          {m.retry && (
            <button type="button" className="act retry" onClick={m.retry}>{t("retry")}</button>
          )}
          <Time at={m.at} />
        </BotRow>
      );
    }
  }
}

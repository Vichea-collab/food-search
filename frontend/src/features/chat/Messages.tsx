import type { ReactNode } from "react";
import { Avatar } from "../../components/Avatar";
import { Icon } from "../../components/Icon";
import { Markdown } from "../../components/Markdown";
import { useI18n } from "../../i18n/I18nContext";
import { timeText } from "../../lib/format";
import type { ChatResponse } from "../../lib/types";
import { PlaceList } from "./PlaceCard";
import { RecipeCard } from "./RecipeCard";
import { VoiceBubble } from "./VoiceBubble";
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

/** Follow-up questions as buttons ("How do I make it?", "Where can I eat it near me?"): sent as normal messages. */
/** Earlier corrections of this answer, sent by users with /correction. */
function Corrections({ items }: { items?: string[] }) {
  if (!items?.length) return null;
  return (
    <>
      {items.map((c) => (
        <p key={c} className="note correction-note">{c}</p>
      ))}
    </>
  );
}

function AskNext({ items, onAsk }: { items?: string[]; onAsk: (q: string) => void }) {
  const { t } = useI18n();
  if (!items?.length) return null;
  return (
    <>
      <p className="note">{t("askNext")}</p>
      <div className="suggest ask-next">
        {items.map((q) => (
          <button key={q} type="button" onClick={() => onAsk(q)}>{q}</button>
        ))}
      </div>
    </>
  );
}

/** The dish in a photo: what it is (and how sure), other guesses to tap, then only what was asked
 *  (the recipe, or places that serve it) and the follow-up questions. */
function DishReply({ data, at, onPickDish, onAsk }: {
  data: ChatResponse; at: Date; onPickDish: (id: string, name: string, photoId?: string | null) => void; onAsk: (q: string) => void;
}) {
  const { t } = useI18n();
  const dish = data.dish!;
  const results = data.results ?? [];
  const byAi = data.provider === "gemini" || data.provider === "ollama";
  // other guesses ("Not it? Maybe:"): always, unless the model is very sure (90%+) and they are near 0%
  const others = dish.alternatives.filter((a) => (dish.confidence ?? 1) < 0.9 || a.confidence >= 0.05);
  return (
    <BotRow>
      <div className="bubble answer dish-lead">
        {byAi && <AiBadge />}
        <Markdown text={data.answer ?? dish.name} />
        {dish.model && <p className="dish-model">{t("dishBy", { m: dish.model })}</p>}
      </div>
      {others.length > 0 && (
        <>
          <p className="note">{t("dishOthers")}</p>
          <div className="suggest dish-others">
            {others.map((a) => (
              <button key={a.id} type="button" onClick={() => onPickDish(a.id, a.name, dish.photo_id)}>
                {a.name} <span className="pct">{Math.min(99, Math.round(a.confidence * 100))}%</span>
              </button>
            ))}
          </div>
        </>
      )}
      {data.recipe && <RecipeCard recipe={data.recipe} focus={data.focus} />}
      {data.no_match && <div className="bubble">{data.no_match}</div>}
      {results.length > 0 && <PlaceList places={results} />}
      <AskNext items={data.suggestions} onAsk={onAsk} />
      <Time at={at} model={byAi ? data.model_label : null} />
    </BotRow>
  );
}

/** An answer about a dish's recipe ("how long does it take?"), with the recipe card under it. */
function RecipeReply({ data, at, onAsk }: { data: ChatResponse; at: Date; onAsk: (q: string) => void }) {
  const byAi = data.provider === "gemini" || data.provider === "ollama";
  return (
    <BotRow>
      <div className="bubble answer">
        {byAi && <AiBadge />}
        <Markdown text={data.answer ?? ""} />
      </div>
      <Corrections items={data.corrections} />
      {data.recipe && <RecipeCard recipe={data.recipe} focus={data.focus} />}
      <AskNext items={data.suggestions} onAsk={onAsk} />
      <Time at={at} model={byAi ? data.model_label : null} />
    </BotRow>
  );
}

function Reply({ data, at, onPickDish, onAsk }: {
  data: ChatResponse; at: Date; onPickDish: (id: string, name: string, photoId?: string | null) => void; onAsk: (q: string) => void;
}) {
  const { t } = useI18n();
  if (data.kind === "dish" && data.dish) return <DishReply data={data} at={at} onPickDish={onPickDish} onAsk={onAsk} />;
  if (data.kind === "recipe") return <RecipeReply data={data} at={at} onAsk={onAsk} />;
  if (data.pick_dishes) {                       // "no, that's wrong": which dish is it?
    return (
      <BotRow>
        <div className="bubble answer">
          <Markdown text={data.answer ?? ""} />
        </div>
        {data.pick_dishes.length > 0 && (
          <div className="suggest dish-others">
            {data.pick_dishes.map((a) => (
              <button key={a.id} type="button" onClick={() => onPickDish(a.id, a.name, data.photo_id)}>
                {a.name} <span className="pct">{Math.min(99, Math.round(a.confidence * 100))}%</span>
              </button>
            ))}
          </div>
        )}
        <Time at={at} model={null} />
      </BotRow>
    );
  }
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
        <Corrections items={data.corrections} />
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
      <Corrections items={data.corrections} />
      {results.length > 0 && <PlaceList places={results} />}
      <Time at={at} model={byAi ? data.model_label : null} />
    </BotRow>
  );
}

/** The spoken answer, above the written one: a voice message (it starts by itself: the user just tapped
 *  "Reply as voice"), shown "preparing…" until the audio is ready, or a note when it could not be made. */
function SpokenAnswer({ audio }: { audio: NonNullable<Extract<Message, { kind: "reply" }>["audio"]> }) {
  const { t } = useI18n();
  return (
    <div className="msg bot spoken">
      <div className="msg-body">
        {audio.state === "failed"
          ? <p className="note">{t("voiceFailed")}</p>
          : <VoiceBubble url={audio.state === "ready" ? audio.url : null} autoPlay label={t("voiceListen")} />}
      </div>
    </div>
  );
}

export function MessageView({
  message: m,
  onSuggestion,
  onPickDish,
  onChooseVoice,
}: {
  message: Message;
  onSuggestion: (q: string) => void;
  onPickDish: (id: string, name: string, photoId?: string | null) => void;
  onChooseVoice: (id: number, text: string, mode: "text" | "voice") => void;
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
    case "user-voice":
      return (
        <UserRow>
          <VoiceBubble url={m.url} mine label={t("voiceMine")} transcript={m.text} />
          <Time at={m.at} />
        </UserRow>
      );
    case "voice-choice":
      return (
        <BotRow>
          <div className="bubble">{t("voiceHeard")}</div>
          <div className="suggest voice-choice">
            <button type="button" onClick={() => onChooseVoice(m.id, m.text, "text")}>{t("voiceAsText")}</button>
            <button type="button" onClick={() => onChooseVoice(m.id, m.text, "voice")}>
              <Icon name="speaker" /> {t("voiceAsVoice")}
            </button>
          </div>
        </BotRow>
      );
    case "user-photo":
      return (
        <UserRow>
          <img className="bubble" src={m.url} alt="" />
          {m.text && <div className="bubble photo-caption">{m.text}</div>}
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
      return (
        <>
          {m.audio && <SpokenAnswer audio={m.audio} />}
          <Reply data={m.data} at={m.at} onPickDish={onPickDish} onAsk={onSuggestion} />
        </>
      );
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

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Avatar } from "../../components/Avatar";
import { Icon } from "../../components/Icon";
import { useI18n } from "../../i18n/I18nContext";
import { htmlLang } from "../../i18n/strings";
import { MessageView } from "./Messages";
import type { Message, ScrollRequest } from "./useChat";

const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");

/** The scrolling list of messages, the empty-state hero, and the "go to the latest message" button. */
export function Thread({
  messages,
  busy,
  scroll,
  onSuggestion,
  onPickDish,
}: {
  messages: Message[];
  busy: boolean;
  scroll: ScrollRequest | null;
  onSuggestion: (q: string) => void;
  onPickDish: (id: string, name: string) => void;
}) {
  const { t, lang } = useI18n();
  const ref = useRef<HTMLElement>(null);
  const items = useRef(new Map<number, HTMLDivElement>());
  const [farFromEnd, setFarFromEnd] = useState(false);

  // a new reply: show its start (long answers are read from the top); while typing: the end
  useLayoutEffect(() => {
    const thread = ref.current;
    if (!thread || !scroll) return;
    if (scroll.mode === "end") thread.scrollTop = thread.scrollHeight;
    else items.current.get(scroll.id)?.scrollIntoView({ block: "start", behavior: reduceMotion.matches ? "auto" : "smooth" });
  }, [scroll]);

  useEffect(() => {
    const thread = ref.current;
    if (!thread) return;
    const onScroll = () => setFarFromEnd(thread.scrollHeight - thread.scrollTop - thread.clientHeight > 300);
    thread.addEventListener("scroll", onScroll, { passive: true });
    return () => thread.removeEventListener("scroll", onScroll);
  }, []);

  const onlyGreeting = messages.length === 1 && messages[0].kind === "greeting";
  return (
    <>
      <main className="thread" ref={ref} aria-live="polite" aria-busy={busy}>
        <div className="thread-inner">
          {onlyGreeting && (
            <div className="intro">
              <Avatar size="xl" />
              <h1 className="intro-name" lang={htmlLang(lang)}>{t("appName")}</h1>
              <p className="intro-role">{t("role")}</p>
            </div>
          )}
          {messages.map((m) => (
            <div
              key={m.id}
              className="msg-wrap"
              ref={(el) => {
                if (el) items.current.set(m.id, el);
                else items.current.delete(m.id);
              }}
            >
              <MessageView message={m} onSuggestion={onSuggestion} onPickDish={onPickDish} />
            </div>
          ))}
        </div>
      </main>
      {farFromEnd && (
        <button
          type="button"
          className="to-bottom"
          aria-label={t("latest")}
          onClick={() => ref.current && (ref.current.scrollTop = ref.current.scrollHeight)}
        >
          <Icon name="down" />
        </button>
      )}
    </>
  );
}

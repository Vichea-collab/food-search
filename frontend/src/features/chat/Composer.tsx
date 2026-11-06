import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Icon } from "../../components/Icon";
import { useI18n } from "../../i18n/I18nContext";
import type { ModelOption } from "../../lib/types";

const MAX_HEIGHT = 132;

function shortModelName(label?: string | null): string {
  if (!label) return "AI";
  if (/no ai/i.test(label) || /none/i.test(label)) return "No AI";
  const geminiMatch = label.match(/Gemini\s+[\d.]+\s*(.+)/i) || label.match(/Gemini\s+(.+)/i);
  if (geminiMatch && geminiMatch[1]) {
    return geminiMatch[1].trim();
  }
  const clean = label.replace(/\s*\(Ollama\)/i, "").trim();
  if (clean.length > 12) {
    return clean.slice(0, 11) + "…";
  }
  return clean || label;
}

/** The message box: grows with the text, Enter sends (Shift+Enter = new line), optional photo search and model switch pill. */
export function Composer({
  busy,
  photoSearch,
  onSend,
  onPhoto,
  models,
  currentModel,
  noAi,
  onModel,
}: {
  busy: boolean;
  photoSearch: boolean;
  onSend: (text: string) => void;
  onPhoto: (file: File) => void;
  models?: ModelOption[];
  currentModel?: string;
  noAi?: string;
  onModel?: (id: string) => void;
}) {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const currentOption = models?.find((m) => m.id === currentModel);
  const currentLabel = currentModel === noAi ? t("noAi") : currentOption?.label ?? currentModel ?? "AI";
  const shortName = shortModelName(currentLabel);

  const resize = () => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  };

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (busy || !text.trim()) return;
    onSend(text);
    setText("");
    requestAnimationFrame(resize);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) submit(e);
  };

  return (
    <form className="composer" autoComplete="off" onSubmit={submit}>
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onPhoto(file);
          e.target.value = "";
        }}
      />
      <div className="composer-box">
        {photoSearch && (
          <button type="button" className="icon-btn ghost photo-btn" aria-label={t("photo")} disabled={busy}
                  onClick={() => fileInput.current?.click()}>
            <Icon name="camera" />
          </button>
        )}
        <label className="sr-only" htmlFor="q">{t("placeholder")}</label>
        <textarea
          id="q"
          ref={box}
          rows={1}
          maxLength={200}
          enterKeyHint="send"
          placeholder={t("placeholder")}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            resize();
          }}
          onKeyDown={onKeyDown}
        />
        {text && !busy && (
          <button
            type="button"
            className="icon-btn ghost clear-btn"
            aria-label={t("clear")}
            title={t("clear")}
            onClick={() => {
              setText("");
              if (box.current) {
                box.current.style.height = "auto";
                box.current.focus();
              }
            }}
          >
            <Icon name="close" />
          </button>
        )}
        {models && models.length > 0 && onModel && (
          <div className="model-pill" title={`${t("aiModel")}: ${currentLabel}`}>
            <span className="model-pill-name">{shortName}</span>
            <Icon name="chevronDown" className="model-pill-ico" />
            <select
              className="model-pill-select"
              aria-label={t("aiModel")}
              value={currentModel}
              onChange={(e) => onModel(e.target.value)}
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
              {noAi && <option value={noAi}>{t("noAi")}</option>}
            </select>
          </div>
        )}
        <button type="submit" className="send-btn" aria-label={t("send")} disabled={busy || !text.trim()}>
          <Icon name="send" />
        </button>
      </div>
    </form>
  );
}

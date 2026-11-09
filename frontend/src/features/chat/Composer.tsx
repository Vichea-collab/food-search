import { useEffect, useRef, useState, type ClipboardEvent, type FormEvent, type KeyboardEvent } from "react";
import { Icon, type IconName } from "../../components/Icon";
import { useI18n } from "../../i18n/I18nContext";
import type { StringKey } from "../../i18n/strings";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { startRecording, voiceSupported, type Recording } from "../../lib/voice";
import type { ModelOption } from "../../lib/types";

const MAX_HEIGHT = 132;

/** The commands of the "/" menu, as in the Telegram bot's menu. */
type CommandName = "correction" | "new" | "photo";
const COMMANDS: { name: CommandName; label: StringKey; icon: IconName }[] = [
  { name: "correction", label: "cmdCorrection", icon: "edit" },
  { name: "new", label: "cmdNew", icon: "plus" },
  { name: "photo", label: "cmdPhoto", icon: "camera" },
];

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

/** The message box: grows with the text, Enter sends (Shift+Enter = new line), model switch pill, and a food photo
 *  that waits in a preview until it is sent, with an optional question typed in the box ("where can I eat this?").
 *  "/" (the button, or typed first) opens the command menu: /correction, /new, /photo. While the bot waits for the
 *  right answer of a /correction, a bar above the box says so (the next message is that answer). */
export function Composer({
  busy,
  photoSearch,
  voiceOn,
  onSend,
  onPhoto,
  onVoice,
  models,
  currentModel,
  noAi,
  onModel,
  onNewChat,
  correcting,
  onCancelCorrection,
}: {
  busy: boolean;
  photoSearch: boolean;
  /** speaking a question is on (the server has voice, and this browser can record) */
  voiceOn: boolean;
  onSend: (text: string) => void;
  onPhoto: (file: File, question: string) => void;
  /** a recorded question (a WAV): the chat turns it into text */
  onVoice: (wav: Blob) => void;
  models?: ModelOption[];
  currentModel?: string;
  noAi?: string;
  onModel?: (id: string) => void;
  onNewChat?: () => void;
  correcting?: { hint: string | null } | null;
  onCancelCorrection?: () => void;
}) {
  const { t } = useI18n();
  const narrow = useMediaQuery("(max-width: 440px)");    // phones: a placeholder that fits
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState<{ file: File; url: string } | null>(null);   // chosen, not sent yet
  const box = useRef<HTMLTextAreaElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const form = useRef<HTMLFormElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);     // opened with the "/" button
  const [dismissed, setDismissed] = useState(false);   // Esc on a typed "/…"
  const [active, setActive] = useState(0);
  // the microphone: idle -> recording (a level meter and a timer) -> sent; a denied microphone shows a note
  const [rec, setRec] = useState<{ level: number; seconds: number } | null>(null);
  const [micError, setMicError] = useState(false);
  const recording = useRef<Recording | null>(null);
  const canSpeak = voiceOn && voiceSupported();

  const commands = COMMANDS.filter((c) => c.name !== "photo" || photoSearch);
  const typed = !photo && /^\/\S*$/.test(text) ? text.slice(1).toLowerCase() : null;   // "/cor" typed so far
  const shown = typed !== null ? commands.filter((c) => c.name.startsWith(typed)) : commands;
  const menuShown = (menuOpen || (typed !== null && !dismissed)) && shown.length > 0 && !busy;

  const currentOption = models?.find((m) => m.id === currentModel);
  const currentLabel = currentModel === noAi ? t("noAi") : currentOption?.label ?? currentModel ?? "AI";
  const shortName = shortModelName(currentLabel);

  const resize = () => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  };

  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo.url); }, [photo]);
  useEffect(() => () => recording.current?.cancel(), []);           // leaving the page: release the microphone
  useEffect(() => {
    if (!rec) return;
    const tick = window.setInterval(() => setRec((r) => (r ? { ...r, seconds: r.seconds + 1 } : r)), 1000);
    return () => window.clearInterval(tick);
  }, [rec !== null]);                                                // eslint-disable-line react-hooks/exhaustive-deps

  const finishRecording = async () => {
    const current = recording.current;
    recording.current = null;
    setRec(null);
    const wav = await current?.stop();
    if (wav) onVoice(wav);
  };
  const toggleMic = async () => {
    if (recording.current) return void finishRecording();
    if (busy) return;
    setMicError(false);
    try {
      const r = await startRecording();
      recording.current = r;
      r.onLevel((level) => setRec((s) => (s ? { ...s, level } : s)));
      r.onLimit(() => void finishRecording());                       // the maximum length: send what was said
      setRec({ level: 0, seconds: 0 });
    } catch {
      setMicError(true);                                               // blocked, or no microphone
    }
  };
  const cancelMic = () => {
    recording.current?.cancel();
    recording.current = null;
    setRec(null);
  };
  useEffect(() => { if (correcting) box.current?.focus(); }, [correcting]);   // ready for the right answer
  useEffect(() => { setActive(0); }, [typed, menuOpen]);
  useEffect(() => {                                    // a tap outside closes the menu
    if (!menuShown) return;
    const close = (e: PointerEvent) => {
      if (!form.current?.contains(e.target as Node)) {
        setMenuOpen(false);
        setDismissed(true);
      }
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [menuShown]);

  const clearText = () => {
    setText("");
    requestAnimationFrame(resize);
  };

  const runCommand = (name: CommandName) => {
    setMenuOpen(false);
    clearText();
    if (name === "correction") onSend("/correction");          // the bot asks what the right answer is
    else if (name === "new") onNewChat?.();
    else fileInput.current?.click();
    if (name !== "photo") requestAnimationFrame(() => box.current?.focus());
  };

  const attach = (file?: File | null) => {
    if (!file || !file.type.startsWith("image/")) return;
    setPhoto({ file, url: URL.createObjectURL(file) });
    requestAnimationFrame(() => box.current?.focus());     // ready for an optional question
  };

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (busy || (!photo && !text.trim())) return;
    const command = /^\/(new|photo)\s*$/i.exec(text.trim());
    if (photo) {
      onPhoto(photo.file, text.trim());
      setPhoto(null);
    } else if (command && (command[1].toLowerCase() === "new" ? onNewChat : photoSearch)) {
      runCommand(command[1].toLowerCase() as CommandName);       // done here, nothing to ask the server
      return;
    } else {
      onSend(text);
    }
    setText("");
    requestAnimationFrame(resize);
  };

  const onPaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const file = photoSearch ? Array.from(e.clipboardData.files).find((f) => f.type.startsWith("image/")) : null;
    if (file) {
      e.preventDefault();
      attach(file);
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (menuShown) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        setActive((i) => (i + (e.key === "ArrowDown" ? 1 : -1) + shown.length) % shown.length);
        return;
      }
      if ((e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) || e.key === "Tab") {
        e.preventDefault();
        runCommand(shown[Math.min(active, shown.length - 1)].name);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setMenuOpen(false);
        setDismissed(true);
        return;
      }
    }
    if (e.key === "Escape" && correcting) {
      e.preventDefault();
      onCancelCorrection?.();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) submit(e);
  };

  return (
    <form ref={form} className="composer" autoComplete="off" onSubmit={submit}>
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => {
          attach(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      {menuShown && (
        <ul className="cmd-menu" id="cmd-menu" role="listbox" aria-label={t("commands")}>
          {shown.map((c, i) => (
            <li key={c.name} id={`cmd-${c.name}`} role="option" aria-selected={i === active}
                className={i === active ? "active" : undefined}
                onPointerDown={(e) => e.preventDefault()}            // keeps the focus (and keyboard) in the box
                onPointerEnter={() => setActive(i)}
                onClick={() => runCommand(c.name)}>
              <Icon name={c.icon} />
              <span className="cmd-name">/{c.name}</span>
              <span className="cmd-label">{t(c.label)}</span>
            </li>
          ))}
        </ul>
      )}
      {correcting && !photo && (
        <div className="composer-correcting" role="status">
          <Icon name="edit" />
          <p>{t("correcting")}</p>
          <button type="button" onClick={onCancelCorrection}>{t("cancel")}</button>
        </div>
      )}
      {rec && (
        <div className="composer-correcting composer-recording" role="status">
          <span className="rec-dot" style={{ transform: `scale(${1 + rec.level * 0.8})` }} aria-hidden="true" />
          <p>{t("recording")} · {Math.floor(rec.seconds / 60)}:{String(rec.seconds % 60).padStart(2, "0")}</p>
          <button type="button" onClick={cancelMic}>{t("micCancel")}</button>
        </div>
      )}
      {micError && !rec && (
        <div className="composer-correcting" role="alert">
          <Icon name="mic" />
          <p>{t("micDenied")}</p>
          <button type="button" onClick={() => setMicError(false)}>{t("close")}</button>
        </div>
      )}
      {photo && (
        <div className="composer-attach">
          <img src={photo.url} alt="" />
          <p>{t("photoReady")}</p>
          <button type="button" className="icon-btn ghost" aria-label={t("photoRemove")} title={t("photoRemove")}
                  onClick={() => setPhoto(null)}>
            <Icon name="close" />
          </button>
        </div>
      )}
      <div className="composer-box">
        {photoSearch && (
          <button type="button" className="icon-btn ghost photo-btn" aria-label={t("photo")} disabled={busy}
                  onClick={() => fileInput.current?.click()}>
            <Icon name="camera" />
          </button>
        )}
        {!text && !photo && !rec && (     /* only while the box is empty: typing shows the clear button instead (phones are narrow) */
          <button type="button" className="icon-btn ghost cmd-btn" aria-label={t("commands")} title={t("commands")}
                  aria-haspopup="listbox" aria-expanded={menuShown} disabled={busy}
                  onClick={() => {
                    setMenuOpen((open) => !open);
                    setDismissed(false);
                    box.current?.focus();
                  }}>
            <Icon name="slash" />
          </button>
        )}
        <label className="sr-only" htmlFor="q">{t("placeholder")}</label>
        <textarea
          id="q"
          ref={box}
          rows={1}
          maxLength={200}
          enterKeyHint="send"
          placeholder={correcting?.hint && !photo ? correcting.hint
            : t(photo ? (narrow ? "placeholderPhotoShort" : "placeholderPhoto") : narrow ? "placeholderShort" : "placeholder")}
          value={text}
          aria-controls={menuShown ? "cmd-menu" : undefined}
          aria-activedescendant={menuShown ? `cmd-${shown[Math.min(active, shown.length - 1)].name}` : undefined}
          onChange={(e) => {
            setText(e.target.value);
            setDismissed(false);
            setMenuOpen(false);
            resize();
          }}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
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
        {models && models.length > 0 && onModel && !narrow && (     /* phones: chosen in the profile, the box keeps its room */
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
        {canSpeak && !photo && !text.trim() ? (    /* as in Telegram: an empty box shows the microphone where "send" goes */
          <button type="button" className={`send-btn mic-btn${rec ? " recording" : ""}`}
                  aria-label={rec ? t("micStop") : t("mic")} title={rec ? t("micStop") : t("mic")}
                  aria-pressed={!!rec} disabled={busy && !rec} onClick={() => void toggleMic()}>
            <Icon name={rec ? "send" : "mic"} />
          </button>
        ) : (
          <button type="submit" className="send-btn" aria-label={t("send")} disabled={busy || (!photo && !text.trim())}>
            <Icon name="send" />
          </button>
        )}
      </div>
    </form>
  );
}

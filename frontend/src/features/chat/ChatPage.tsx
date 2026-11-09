import { useCallback, useEffect, useRef, useState } from "react";
import { useI18n } from "../../i18n/I18nContext";
import { api } from "../../lib/api";
import { haptic } from "../../lib/telegram";
import { storage } from "../../lib/storage";
import type { AppConfig } from "../../lib/types";
import { ChatHeader, type ShownStatus } from "./ChatHeader";
import { useServerReachable } from "../../lib/useServerReachable";
import { Composer } from "./Composer";
import { LocationSheet } from "./LocationSheet";
import { ProfilePanel, type VoiceGender } from "./ProfilePanel";
import { Thread } from "./Thread";
import { useChat, type LocationChoice, type VoiceReply } from "./useChat";
import "./chat.css";

/** The chat app (website and Telegram Mini App): profile, chat, and the location sheet. */
export function ChatPage() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [model, setModel] = useState<string | null>(() => storage.get("model"));
  const modelRef = useRef(model);
  const [voiceGender, setVoiceGender] = useState<VoiceGender>(() => (storage.get("voice-gender") === "male" ? "male" : "female"));
  const voiceRef = useRef<string>(voiceGender);
  const [voiceReply, setVoiceReply] = useState<VoiceReply>(() => {
    const saved = storage.get("voice-reply");
    return saved === "voice" || saved === "text" ? saved : "ask";
  });
  const voiceReplyRef = useRef<VoiceReply>(voiceReply);
  const [profileOpen, setProfileOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const sheetResolve = useRef<((choice: LocationChoice) => void) | null>(null);

  useEffect(() => {
    api.config().then((c) => {
      setConfig(c);
      setModel((saved) => {
        // a saved model that the server no longer offers falls back to the default
        const ok = saved === c.no_llm || c.models.some((m) => m.id === saved);
        const chosen = ok ? saved : c.default_model;
        modelRef.current = chosen;
        return chosen;
      });
    }).catch(() => { /* offline: the first question will show the error */ });
  }, []);

  const chooseVoiceGender = useCallback((g: VoiceGender) => {
    voiceRef.current = g;
    setVoiceGender(g);
    storage.set("voice-gender", g);
    haptic("select");
  }, []);

  const chooseVoiceReply = useCallback((mode: VoiceReply) => {
    voiceReplyRef.current = mode;
    setVoiceReply(mode);
    storage.set("voice-reply", mode);
    haptic("select");
  }, []);

  const chooseModel = useCallback((id: string) => {
    modelRef.current = id;
    setModel(id);
    storage.set("model", id);
    haptic("select");
  }, []);

  const askLocation = useCallback(
    () => new Promise<LocationChoice>((resolve) => {
      sheetResolve.current = resolve;
      setSheetOpen(true);
    }),
    [],
  );
  const onSheetDone = useCallback((choice: LocationChoice) => {
    setSheetOpen(false);
    sheetResolve.current?.(choice);
    sheetResolve.current = null;
  }, []);

  const { lang } = useI18n();
  const langRef = useRef<string>(lang);
  useEffect(() => {
    langRef.current = lang;
  }, [lang]);
  const chat = useChat({ askLocation, modelRef, langRef, voiceRef, voiceReplyRef });
  const serverUp = useServerReachable();
  const status: ShownStatus = serverUp ? chat.status : "offline";

  const closeProfile = useCallback(() => {
    setProfileOpen(false);
    document.querySelector<HTMLButtonElement>(".who")?.focus(); // back to the button that opened it
  }, []);

  return (
    <div className="app">
      <ProfilePanel
        open={profileOpen}
        onClose={closeProfile}
        status={status}
        config={config}
        model={model}
        onModel={chooseModel}
        voiceGender={voiceGender}
        onVoiceGender={chooseVoiceGender}
        voiceReply={voiceReply}
        onVoiceReply={chooseVoiceReply}
        location={chat.location}
        onLocationOff={() => chat.setLocation(null)}
        recent={chat.recent}
        onAsk={(q) => {
          setProfileOpen(false);
          chat.send(q);
        }}
        onNewChat={() => {
          setProfileOpen(false);
          chat.newChat();
        }}
      />
      <section className="chat" aria-label="Chat">
        <ChatHeader status={status} profileOpen={profileOpen} onOpenProfile={() => setProfileOpen(true)} />
        <Thread messages={chat.messages} busy={chat.busy} scroll={chat.scroll} onSuggestion={chat.send}
                onPickDish={chat.pickDish} onChooseVoice={chat.chooseVoice} />
        <Composer
          busy={chat.busy}
          photoSearch={!!config?.photo_search}
          voiceOn={!!config?.voice}
          onSend={chat.send}
          onPhoto={chat.sendPhoto}
          onVoice={chat.sendVoice}
          models={config?.models ?? []}
          currentModel={model ?? config?.default_model ?? ""}
          noAi={config?.no_llm}
          onModel={chooseModel}
          onNewChat={chat.newChat}
          correcting={chat.correcting}
          onCancelCorrection={chat.cancelCorrection}
        />
      </section>
      <LocationSheet open={sheetOpen} onLocated={chat.setLocation} onDone={onSheetDone} />
    </div>
  );
}

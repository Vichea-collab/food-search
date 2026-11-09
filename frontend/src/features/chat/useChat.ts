/** The conversation: messages, the bot's status, sending questions and photos, and the "near me" location step. */
import { useCallback, useRef, useState, type MutableRefObject } from "react";
import { api, ApiError, type Turn } from "../../lib/api";
import { withPlace } from "../../lib/format";
import { haptic } from "../../lib/telegram";
import type { ChatResponse, Coords } from "../../lib/types";

export type Status = "online" | "typing" | "locating";
export type LocationChoice = { kind: "loc" } | { kind: "place"; place: string } | { kind: "skip" };

/** The spoken version of a reply: being made, ready (an object URL of the MP3), or failed. */
/** How a spoken question is answered: ask "text or voice?" each time, or always one of them. */
export type VoiceReply = "ask" | "voice" | "text";

/** An answer worked out while the user is still choosing "text or voice?" (and its voice, made meanwhile). */
interface Ahead {
  first: Promise<ChatResponse>;
  audio: Promise<string | null>;
  turns: number;          // the conversation length then: if it changed, the answer is stale and is asked again
}

export type AudioState = { state: "loading" } | { state: "ready"; url: string } | { state: "failed" };

export type Message =
  | { id: number; kind: "greeting"; at: Date }
  | { id: number; kind: "user-text"; text: string; at: Date }
  /** the user's recorded question, shown as a voice message (url: the recording; its words are not shown) */
  | { id: number; kind: "user-voice"; url: string; text?: string; at: Date }
  | { id: number; kind: "voice-choice"; text: string; at: Date }
  | { id: number; kind: "user-photo"; url: string; text?: string; at: Date }
  | { id: number; kind: "pending" }
  | { id: number; kind: "reply"; data: ChatResponse; audio?: AudioState; at: Date }
  | { id: number; kind: "error"; error: ApiError; retry?: () => void; at: Date };

/** Which message the thread should scroll to: the end (while typing) or the start of a new reply. */
export interface ScrollRequest {
  id: number;
  mode: "end" | "start";
}

const RECENT_MAX = 8;
const HISTORY_MAX = 12;        // messages sent with each question (the server uses the last 12)
const CONTEXT_MAX = 10;        // places a follow-up question can refer to ("number 7")

/** What the assistant said, as plain text for the conversation history (names + numbers of the places shown). */
function summary(data: ChatResponse): string {
  const places = (data.results ?? []).slice(0, 5)
    .map((p, i) => `${data.numbers?.[i] ?? i + 1}. ${p.name} (${[p.dish, p.area].filter(Boolean).join(", ")})`).join("; ");
  return [data.answer ?? "", places && `Places shown: ${places}`].filter(Boolean).join(" ");
}
let lastId = 0;
const nextId = () => ++lastId;
const t_unclear = (lang: string) => (lang === "kh"
  ? "ខ្ញុំស្តាប់មិនបានទេ។ សូមព្យាយាមម្តងទៀត ឬវាយសំណួររបស់អ្នក។"
  : "I couldn’t hear that. Please try again, or type your question.");
const greeting = (): Message => ({ id: nextId(), kind: "greeting", at: new Date() });

export function useChat({
  askLocation,
  modelRef,
  langRef,
  voiceRef,
  voiceReplyRef,
}: {
  /** Opens the location sheet and resolves with the user's choice. */
  askLocation: () => Promise<LocationChoice>;
  /** The chosen AI model id (a ref, so a change applies to the next question without re-creating callbacks). */
  modelRef: MutableRefObject<string | null>;
  /** The UI language: a photo has no words, so its reply uses this one. */
  langRef: MutableRefObject<string>;
  /** The chosen voice for spoken answers: "female" or "male". */
  voiceRef: MutableRefObject<string>;
  /** How spoken questions are answered (see VoiceReply). */
  voiceReplyRef: MutableRefObject<VoiceReply>;
}) {
  const [messages, setMessages] = useState<Message[]>(() => [greeting()]);
  const [status, setStatus] = useState<Status>("online");
  const [busy, setBusy] = useState(false);
  const [recent, setRecent] = useState<string[]>([]);
  const [location, setLocationState] = useState<Coords | null>(null);
  const [scroll, setScroll] = useState<ScrollRequest | null>(null);
  const busyRef = useRef(false);
  const locationRef = useRef<Coords | null>(null); // memory only: never written to storage
  // the conversation, sent with every question (memory only, cleared by "New chat")
  const historyRef = useRef<Turn[]>([]);
  const contextIdsRef = useRef<string[]>([]);
  const lastQueryRef = useRef<string | null>(null);
  const dishRef = useRef<string | null>(null);     // the dish of the last photo: "how long does it take?" is about it
  const photoRef = useRef<string | null>(null);    // the last photo: "no, it's amok" corrects it
  const answeredRef = useRef<string | null>(null); // the question the last answer was for: "/correction …" corrects it
  // the bot asked "what is the right answer?" (a bare /correction, or "no" after a photo): the next message is it
  const awaitingRef = useRef(false);
  const aheadRef = useRef(new Map<number, Ahead>());   // voice-choice id -> the answer being found meanwhile
  const [correcting, setCorrecting] = useState<{ hint: string | null } | null>(null);
  const stopCorrecting = useCallback(() => {
    awaitingRef.current = false;
    setCorrecting(null);
  }, []);

  const rememberTurn = useCallback((question: string, data: ChatResponse, searched: string) => {
    historyRef.current = [...historyRef.current, { role: "user" as const, text: question },
                          { role: "assistant" as const, text: summary(data) }].slice(-HISTORY_MAX);
    if (data.kind !== "followup" && data.kind !== "chat" && data.results?.length) {   // a new list of places
      contextIdsRef.current = data.results.slice(0, CONTEXT_MAX).map((p) => p.id);
      lastQueryRef.current = searched;
    }
    if (data.dish) dishRef.current = data.dish.id;                       // a photo, a picked dish, a recipe answer
    else if (data.kind === "search" && data.results?.length) dishRef.current = null;   // moved on to other food
    // the photo a correction ("no, it's amok", "/correction amok") refers to: only while the last answer is about it;
    // after any other answer, /correction corrects that answer instead
    photoRef.current = data.dish?.photo_id ?? data.photo_id ?? null;
    if (data.provider !== "correction") answeredRef.current = searched || question;
  }, []);

  const setLocation = useCallback((coords: Coords | null) => {
    locationRef.current = coords;
    setLocationState(coords);
  }, []);

  const replace = (id: number, msg: Message | null) =>
    setMessages((list) => (msg ? list.map((m) => (m.id === id ? msg : m)) : list.filter((m) => m.id !== id)));

  /** Reads a reply aloud (the short answer and the first place names): the player appears under it. */
  const speakReply = useCallback(async (id: number, data: ChatResponse, made?: Promise<string | null>) => {
    const set = (audio: AudioState) =>
      setMessages((list) => list.map((m) => (m.id === id && m.kind === "reply" ? { ...m, audio } : m)));
    try {
      const names = (data.results ?? []).slice(0, 3).map((p) => p.name);
      const url = (made && await made) || await api.speak(data.answer ?? "", data.lang ?? langRef.current, voiceRef.current, names);
      set({ state: "ready", url });
    } catch {
      set({ state: "failed" });
    }
  }, [langRef, voiceRef]);

  /** Shows "typing…", runs `work`, then replaces the typing bubble with the reply or an error. */
  const run = useCallback(async (work: () => Promise<ChatResponse | null>, retry: () => void, speak = false,
                               made?: Promise<string | null>) => {
    const id = nextId();
    busyRef.current = true;
    setBusy(true);
    setStatus("typing");
    setMessages((list) => [...list, { id, kind: "pending" }]);
    setScroll({ id, mode: "end" });
    try {
      const data = await work();
      replace(id, data ? { id, kind: "reply", data, at: new Date(), audio: speak && data.answer ? { state: "loading" } : undefined } : null);
      if (data) {
        setScroll({ id, mode: "start" });
        haptic("success");
        if (speak && data.answer) void speakReply(id, data, made);
      }
    } catch (e) {
      haptic("error");
      const error = e instanceof ApiError ? e : new ApiError("server");
      const again = error.kind === "client" ? undefined : () => {
        replace(id, null);
        retry();
      };
      replace(id, { id, kind: "error", error, retry: again, at: new Date() });
    } finally {
      busyRef.current = false;
      setBusy(false);
      setStatus("online");
    }
  }, [speakReply]);

  /** Asks the server (with the conversation so far); for "… near me" without a location, opens the location
   *  sheet and then searches directly. */
  const chatBody = useCallback((query: string) => ({
    query, location: locationRef.current, model: modelRef.current, history: historyRef.current,
    context_ids: contextIdsRef.current, last_query: lastQueryRef.current, dish_id: dishRef.current,
    photo_id: photoRef.current, last_question: answeredRef.current,
  }), [modelRef]);

  const ask = useCallback(
    async (query: string, first?: Promise<ChatResponse>) => {
      const base = { location: locationRef.current, model: modelRef.current };
      let searched = query;
      let data = await (first ?? api.chat(chatBody(query)));         // first: already asked while the user chose
      if (data.need_location) {
        searched = data.search_query || query;
        setStatus("locating");
        const choice = await askLocation();
        setStatus("typing");
        if (choice.kind === "place") searched = withPlace(searched, choice.place);
        data = await api.chat({ query: searched, ...base, location: locationRef.current, direct: true,
                                no_location: choice.kind === "skip" });
        if (searched !== query) data = { ...data, search_query: searched };       // show what was searched
      } else if (data.search_query) {
        searched = data.search_query;
      }
      if (data.awaiting === "correction") {
        awaitingRef.current = true;
        setCorrecting({ hint: data.hint ?? null });
        // only a question from the bot: the conversation stays as it was, so the answer corrects the right thing
        if (data.provider === "correction") return data;
      }
      rememberTurn(query, data, searched);
      return data;
    },
    [askLocation, modelRef, rememberTurn, chatBody],
  );

  const send = useCallback(
    (text: string, isRetry = false, asCorrection = false, speak = false,
     ahead?: { first: Promise<ChatResponse>; audio?: Promise<string | null> }) => {
      const query = text.trim().slice(0, 200);
      if (!query || busyRef.current) return;
      // the answer to "what is the right answer?": sent as "/correction <it>", shown as typed
      const correction = asCorrection || (awaitingRef.current && !query.startsWith("/"));
      stopCorrecting();
      haptic("tap");
      if (!isRetry) {
        setMessages((list) => [...list, { id: nextId(), kind: "user-text", text: query, at: new Date() }]);
        setRecent((list) => [query, ...list.filter((q) => q !== query)].slice(0, RECENT_MAX));
      }
      const asked = correction ? `/correction ${query}` : query;
      void run(() => ask(asked, correction ? undefined : ahead?.first), () => send(query, true, correction, speak), speak,
               ahead?.audio);
    },
    [ask, run, stopCorrecting],
  );

  /** A food photo, with an optional question. "… near me" without a location: the location sheet first, then the
   *  search runs as a normal chat search, under the photo's "this looks like …" line. */
  const sendPhoto = useCallback(
    (file: File, question = "", isRetry = false) => {
      if (busyRef.current) return;
      stopCorrecting();                                  // a new photo, not the answer
      haptic("tap");
      if (!isRetry) {
        setMessages((list) => [...list, { id: nextId(), kind: "user-photo", url: URL.createObjectURL(file),
                                          text: question || undefined, at: new Date() }]);
      }
      void run(async () => {
        let data = await api.photo(file, langRef.current,
                                   { location: locationRef.current, query: question, model: modelRef.current });
        let searched = data.search_query || data.dish?.name || "";
        if (data.need_location && data.search_query) {
          setStatus("locating");
          const choice = await askLocation();
          setStatus("typing");
          searched = choice.kind === "place" ? withPlace(data.search_query, choice.place) : data.search_query;
          const found = await api.chat({ query: searched, location: locationRef.current, model: modelRef.current,
                                         direct: true, no_location: choice.kind === "skip" });
          data = { ...found, kind: "dish", dish: data.dish, search_query: searched,
                   answer: [data.answer, found.answer ?? found.no_match].filter(Boolean).join("\n\n") };
        }
        rememberTurn(question || "(a food photo)", data, searched);
        return data;
      }, () => sendPhoto(file, question, true));
    },
    [run, rememberTurn, langRef, modelRef, askLocation, stopCorrecting],
  );

  /** A recorded question: shown at once as the user's voice message, turned into text behind the scenes, then
   *  "reply as text or as voice?". While the bot waits for the right answer of a /correction, the words are that
   *  answer and there is nothing to choose. */
  const sendVoice = useCallback(
    async (wav: Blob) => {
      if (busyRef.current) return;
      haptic("tap");
      const id = nextId();
      busyRef.current = true;
      setBusy(true);
      setStatus("typing");
      const mine = nextId();
      setMessages((list) => [...list, { id: mine, kind: "user-voice", url: URL.createObjectURL(wav), at: new Date() },
                             { id, kind: "pending" }]);
      setScroll({ id, mode: "end" });
      try {
        const { text } = await api.transcribe(wav, langRef.current);
        const heard = text.trim().slice(0, 200);
        if (!heard) throw new ApiError("client", t_unclear(langRef.current));
        busyRef.current = false;
        setBusy(false);
        setStatus("online");
        // the words stay hidden under the user's voice message ("Aa" shows them)
        setMessages((list) => list.map((m) => (m.id === mine && m.kind === "user-voice" ? { ...m, text: heard } : m)));
        const mode = voiceReplyRef.current;
        if (awaitingRef.current || mode !== "ask") {      // the right answer to "what is it?", or no choice to make
          setMessages((list) => list.filter((m) => m.id !== id));
          send(heard, true, false, !awaitingRef.current && mode === "voice");
          setRecent((list) => [heard, ...list.filter((q) => q !== heard)].slice(0, RECENT_MAX));
        } else {
          // answer it (and make its voice) while the user chooses: the tap then shows it at once
          const first = api.chat(chatBody(heard));
          first.catch(() => undefined);
          const audio = first.then((d) => (d.answer && !d.need_location && d.awaiting !== "correction"
            ? api.speak(d.answer, d.lang ?? langRef.current, voiceRef.current, (d.results ?? []).slice(0, 3).map((p) => p.name))
            : null)).catch(() => null);
          aheadRef.current.set(id, { first, audio, turns: historyRef.current.length });
          replace(id, { id, kind: "voice-choice", text: heard, at: new Date() });
          setScroll({ id, mode: "end" });
        }
      } catch (e) {
        haptic("error");
        const error = e instanceof ApiError ? e : new ApiError("server");
        setMessages((list) => list.map((m) => (m.id === id ? { id, kind: "error", error, at: new Date() } : m)));
        busyRef.current = false;
        setBusy(false);
        setStatus("online");
      }
    },
    [langRef, send, chatBody, voiceRef, voiceReplyRef],
  );

  /** The two buttons under a transcribed question: the answer found meanwhile is shown (spoken or not), unless the
   *  conversation moved on since, then it is asked again. */
  const chooseVoice = useCallback(
    (id: number, text: string, mode: "text" | "voice") => {
      if (busyRef.current) return;
      const ahead = aheadRef.current.get(id);
      aheadRef.current.delete(id);
      const fresh = ahead && ahead.turns === historyRef.current.length ? ahead : undefined;
      if (ahead && (!fresh || mode === "text")) void ahead.audio.then((url) => url && URL.revokeObjectURL(url));
      setMessages((list) => list.filter((m) => m.id !== id));
      send(text, true, false, mode === "voice",
           fresh && { first: fresh.first, audio: mode === "voice" ? fresh.audio : undefined });
      setRecent((list) => [text, ...list.filter((q) => q !== text)].slice(0, RECENT_MAX));
    },
    [send],
  );

  /** The user tapped another guess for their photo (photoId: that photo, so the app learns the correction). */
  const pickDish = useCallback(
    (id: string, name: string, photoId?: string | null) => {
      if (busyRef.current) return;
      stopCorrecting();                                  // tapping a guess answers "What is it?"
      haptic("tap");
      setMessages((list) => [...list, { id: nextId(), kind: "user-text", text: name, at: new Date() }]);
      void run(async () => {
        const data = await api.dish(id, langRef.current, locationRef.current, photoId);
        rememberTurn(name, data, name);
        return data;
      }, () => pickDish(id, name, photoId));
    },
    [run, rememberTurn, langRef, stopCorrecting],
  );

  const newChat = useCallback(() => {
    if (busyRef.current) return;
    historyRef.current = [];
    contextIdsRef.current = [];
    lastQueryRef.current = null;
    dishRef.current = null;
    photoRef.current = null;
    answeredRef.current = null;
    stopCorrecting();
    setMessages((list) => {
      list.forEach((m) => {
        if (m.kind === "user-photo" || m.kind === "user-voice") URL.revokeObjectURL(m.url);
        if (m.kind === "reply" && m.audio?.state === "ready") URL.revokeObjectURL(m.audio.url);
      });
      return [greeting()];
    });
  }, [stopCorrecting]);

  return { messages, status, busy, recent, location, setLocation, send, sendPhoto, sendVoice, chooseVoice, pickDish, newChat, scroll,
           correcting, cancelCorrection: stopCorrecting };
}

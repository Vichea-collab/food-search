/** The conversation: messages, the bot's status, sending questions and photos, and the "near me" location step. */
import { useCallback, useRef, useState, type MutableRefObject } from "react";
import { api, ApiError, type Turn } from "../../lib/api";
import { withPlace } from "../../lib/format";
import { haptic } from "../../lib/telegram";
import type { ChatResponse, Coords } from "../../lib/types";

export type Status = "online" | "typing" | "locating";
export type LocationChoice = { kind: "loc" } | { kind: "place"; place: string } | { kind: "skip" };

export type Message =
  | { id: number; kind: "greeting"; at: Date }
  | { id: number; kind: "user-text"; text: string; at: Date }
  | { id: number; kind: "user-photo"; url: string; at: Date }
  | { id: number; kind: "pending" }
  | { id: number; kind: "reply"; data: ChatResponse; at: Date }
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
const greeting = (): Message => ({ id: nextId(), kind: "greeting", at: new Date() });

export function useChat({
  askLocation,
  modelRef,
  langRef,
}: {
  /** Opens the location sheet and resolves with the user's choice. */
  askLocation: () => Promise<LocationChoice>;
  /** The chosen AI model id (a ref, so a change applies to the next question without re-creating callbacks). */
  modelRef: MutableRefObject<string | null>;
  /** The UI language: a photo has no words, so its reply uses this one. */
  langRef: MutableRefObject<string>;
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

  const rememberTurn = useCallback((question: string, data: ChatResponse, searched: string) => {
    historyRef.current = [...historyRef.current, { role: "user" as const, text: question },
                          { role: "assistant" as const, text: summary(data) }].slice(-HISTORY_MAX);
    if (data.kind !== "followup" && data.kind !== "chat" && data.results?.length) {   // a new list of places
      contextIdsRef.current = data.results.slice(0, CONTEXT_MAX).map((p) => p.id);
      lastQueryRef.current = searched;
    }
    if (data.dish) dishRef.current = data.dish.id;                       // a photo, a picked dish, a recipe answer
    else if (data.kind === "search" && data.results?.length) dishRef.current = null;   // moved on to other food
  }, []);

  const setLocation = useCallback((coords: Coords | null) => {
    locationRef.current = coords;
    setLocationState(coords);
  }, []);

  const replace = (id: number, msg: Message | null) =>
    setMessages((list) => (msg ? list.map((m) => (m.id === id ? msg : m)) : list.filter((m) => m.id !== id)));

  /** Shows "typing…", runs `work`, then replaces the typing bubble with the reply or an error. */
  const run = useCallback(async (work: () => Promise<ChatResponse | null>, retry: () => void) => {
    const id = nextId();
    busyRef.current = true;
    setBusy(true);
    setStatus("typing");
    setMessages((list) => [...list, { id, kind: "pending" }]);
    setScroll({ id, mode: "end" });
    try {
      const data = await work();
      replace(id, data ? { id, kind: "reply", data, at: new Date() } : null);
      if (data) {
        setScroll({ id, mode: "start" });
        haptic("success");
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
  }, []);

  /** Asks the server (with the conversation so far); for "… near me" without a location, opens the location
   *  sheet and then searches directly. */
  const ask = useCallback(
    async (query: string) => {
      const base = { location: locationRef.current, model: modelRef.current };
      let searched = query;
      let data = await api.chat({
        query, ...base, history: historyRef.current, context_ids: contextIdsRef.current, last_query: lastQueryRef.current,
        dish_id: dishRef.current,
      });
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
      rememberTurn(query, data, searched);
      return data;
    },
    [askLocation, modelRef, rememberTurn],
  );

  const send = useCallback(
    (text: string, isRetry = false) => {
      const query = text.trim().slice(0, 200);
      if (!query || busyRef.current) return;
      haptic("tap");
      if (!isRetry) {
        setMessages((list) => [...list, { id: nextId(), kind: "user-text", text: query, at: new Date() }]);
        setRecent((list) => [query, ...list.filter((q) => q !== query)].slice(0, RECENT_MAX));
      }
      void run(() => ask(query), () => send(query, true));
    },
    [ask, run],
  );

  const sendPhoto = useCallback(
    (file: File) => {
      if (busyRef.current) return;
      haptic("tap");
      setMessages((list) => [...list, { id: nextId(), kind: "user-photo", url: URL.createObjectURL(file), at: new Date() }]);
      void run(async () => {
        const data = await api.photo(file, langRef.current, locationRef.current);
        rememberTurn("(a food photo)", data, data.dish?.name ?? "");
        return data;
      }, () => sendPhoto(file));
    },
    [run, rememberTurn, langRef],
  );

  /** The user tapped another guess for their photo: that dish's recipe and places. */
  const pickDish = useCallback(
    (id: string, name: string) => {
      if (busyRef.current) return;
      haptic("tap");
      setMessages((list) => [...list, { id: nextId(), kind: "user-text", text: name, at: new Date() }]);
      void run(async () => {
        const data = await api.dish(id, langRef.current, locationRef.current);
        rememberTurn(name, data, name);
        return data;
      }, () => pickDish(id, name));
    },
    [run, rememberTurn, langRef],
  );

  const newChat = useCallback(() => {
    if (busyRef.current) return;
    historyRef.current = [];
    contextIdsRef.current = [];
    lastQueryRef.current = null;
    dishRef.current = null;
    setMessages((list) => {
      list.forEach((m) => m.kind === "user-photo" && URL.revokeObjectURL(m.url));
      return [greeting()];
    });
  }, []);

  return { messages, status, busy, recent, location, setLocation, send, sendPhoto, pickDish, newChat, scroll };
}

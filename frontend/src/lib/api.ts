/** Typed client for the backend API (backend/food_search/api). In development Vite forwards /api to the
 *  Python server; in production the Python server serves this app itself, so paths are always relative. */
import type { AppConfig, ChatResponse, CompareResponse, Coords, DataStats, DemoAskResponse, DemoPhotoResponse } from "./types";
import { inTelegram, tg } from "./telegram";

export class ApiError extends Error {
  /** offline = no connection; client = our request was refused (429 rate limit, 400, …); server = 5xx */
  constructor(public kind: "offline" | "client" | "server", message?: string) {
    super(message ?? kind);
  }
}

/** A random id for this browser, so the app knows that a correction ("/correction …") came from the same person who
 *  asks again. Nothing else is linked to it; without storage it lasts until the page is closed. */
let clientId: string | null = null;
function getClientId(): string {
  if (clientId) return clientId;
  try {
    clientId = localStorage.getItem("kn-client-id");
    if (!clientId) {
      clientId = crypto.randomUUID();
      localStorage.setItem("kn-client-id", clientId);
    }
  } catch {
    clientId = clientId ?? (crypto.randomUUID?.() ?? String(Math.random()).slice(2));
  }
  return clientId;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (inTelegram && tg) headers.set("X-Telegram-Init-Data", tg.initData); // verified on the server with the bot token
  headers.set("X-Client-Id", getClientId());
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError("offline");
  }
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* not JSON */
  }
  if (!res.ok) {
    const message = (data as { message?: string } | null)?.message;
    throw new ApiError(res.status === 429 || res.status < 500 ? "client" : "server", message);
  }
  return data as T;
}

/** Like request(), but the answer is a file (the spoken answer: an MP3). */
async function requestBlob(path: string, init: RequestInit): Promise<Blob> {
  const headers = new Headers(init.headers);
  if (inTelegram && tg) headers.set("X-Telegram-Init-Data", tg.initData);
  headers.set("X-Client-Id", getClientId());
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError("offline");
  }
  if (!res.ok) throw new ApiError(res.status === 429 || res.status < 500 ? "client" : "server");
  return res.blob();
}

const postJson = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export interface Turn {
  role: "user" | "assistant";
  text: string;
}

export interface ChatRequest {
  query: string;
  location?: Coords | null;
  no_location?: boolean;
  model?: string | null;
  /** the conversation (the server keeps no state): recent messages, places shown last, the last search */
  history?: Turn[];
  context_ids?: string[];
  last_query?: string | null;
  /** search `query` as it is, without planning (after the location step) */
  direct?: boolean;
  /** the dish shown last (from a photo), so "how long does it take?" is about it */
  dish_id?: string | null;
  /** the last photo: "no, it's amok" corrects its dish (and the app learns it) */
  photo_id?: string | null;
  /** the question the last answer was for (the search actually run): what "/correction …" corrects */
  last_question?: string | null;
}

export const api = {
  config: () => request<AppConfig>("/api/config"),
  chat: (body: ChatRequest) => postJson<ChatResponse>("/api/chat", body),
  /** A recorded question (a WAV, see lib/voice.ts) -> its words. */
  transcribe: (audio: Blob, lang: string) => {
    const form = new FormData();
    form.append("audio", audio, "question.wav");
    form.append("lang", lang);
    return request<{ text: string; lang: "en" | "kh" }>("/api/voice/transcribe", { method: "POST", body: form });
  },
  /** An answer read aloud: an object URL of the MP3 (revoke it when it is no longer shown). */
  speak: async (text: string, lang: string, gender: string, names: string[] = []) => {
    const blob = await requestBlob("/api/voice/speak", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, lang, gender, names }),
    });
    return URL.createObjectURL(blob);
  },
  /** A food photo, with an optional question about it ("where can I eat this?"). */
  photo: (file: File, lang: string, opts: { location?: Coords | null; query?: string; model?: string | null } = {}) => {
    const form = new FormData();
    form.append("photo", file);
    form.append("lang", lang);
    if (opts.query) form.append("query", opts.query);
    if (opts.model) form.append("model", opts.model);
    if (opts.location) {
      form.append("lat", String(opts.location.lat));
      form.append("lng", String(opts.location.lng));
    }
    return request<ChatResponse>("/api/photo", { method: "POST", body: form });
  },
  /** A dish the user picked (another guess for their photo). With photoId it corrects that photo: the app learns it. */
  dish: (dishId: string, lang: string, location?: Coords | null, photoId?: string | null) =>
    postJson<ChatResponse>("/api/dish", { dish_id: dishId, lang, location: location ?? null, photo_id: photoId ?? null }),
  demoAsk: (query: string, model: string | null) => postJson<DemoAskResponse>("/api/demo/ask", { query, model }),
  demoCompare: (query: string, weight: number) => postJson<CompareResponse>("/api/demo/compare", { query, weight }),
  demoData: () => request<DataStats>("/api/demo/data"),
  /** A photo, with every step of the image classifier (what it sees, top 5, then the dish's recipe and places). */
  demoPhoto: (file: File) => {
    const form = new FormData();
    form.append("photo", file);
    return request<DemoPhotoResponse>("/api/demo/photo", { method: "POST", body: form });
  },
};

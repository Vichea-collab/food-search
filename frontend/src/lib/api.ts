/** Typed client for the backend API (backend/food_search/api). In development Vite forwards /api to the
 *  Python server; in production the Python server serves this app itself, so paths are always relative. */
import type { AppConfig, ChatResponse, CompareResponse, Coords, DataStats, DemoAskResponse } from "./types";
import { inTelegram, tg } from "./telegram";

export class ApiError extends Error {
  /** offline = no connection; client = our request was refused (429 rate limit, 400, …); server = 5xx */
  constructor(public kind: "offline" | "client" | "server", message?: string) {
    super(message ?? kind);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (inTelegram && tg) headers.set("X-Telegram-Init-Data", tg.initData); // verified on the server with the bot token
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
}

export const api = {
  config: () => request<AppConfig>("/api/config"),
  chat: (body: ChatRequest) => postJson<ChatResponse>("/api/chat", body),
  photo: (file: File, lang: string, location?: Coords | null) => {
    const form = new FormData();
    form.append("photo", file);
    form.append("lang", lang);
    if (location) {
      form.append("lat", String(location.lat));
      form.append("lng", String(location.lng));
    }
    return request<ChatResponse>("/api/photo", { method: "POST", body: form });
  },
  /** A dish the user picked (another guess for their photo): its recipe and places. */
  dish: (dishId: string, lang: string, location?: Coords | null) =>
    postJson<ChatResponse>("/api/dish", { dish_id: dishId, lang, location: location ?? null }),
  demoAsk: (query: string, model: string | null) => postJson<DemoAskResponse>("/api/demo/ask", { query, model }),
  demoCompare: (query: string, weight: number) => postJson<CompareResponse>("/api/demo/compare", { query, weight }),
  demoData: () => request<DataStats>("/api/demo/data"),
};

/** Small formatters shared by the chat and the demo. */

/** 0.47 -> "470 m", 1.43 -> "1.4 km", 12.6 -> "13 km" (same format as the bot and the AI prompt). */
export const distanceText = (km: number) =>
  km < 1 ? `${Math.round(km * 100) * 10} m` : `${km < 10 ? km.toFixed(1) : Math.round(km)} km`;

const pad = (h: number) => `${String(Math.round(h) % 24).padStart(2, "0")}:00`;

/** Opening hours, or `allDay` for places open around the clock. Hours may cross midnight (18 -> 2). */
export const hoursText = (open: number, close: number, allDay: string) =>
  (open === 0 && close === 24) || open === close ? allDay : `${pad(open)}–${pad(close)}`;

export const trimNumber = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(2));
export const titleCase = (s: string) => s.replace(/\b\w/g, (c) => c.toUpperCase());

const timeFormat = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });
export const timeText = (date: Date) => timeFormat.format(date);

/** "coffee near me" + typed place "CADT" -> "coffee near CADT" (the server looks the place up on the map). */
const NEAR_ME =
  /\b(?:near\s*me|nearby|near\s+here|around\s+me|around\s+here|close\s+to\s+me|closest|nearest)\b|ជិតខ្ញុំ|នៅជិត|ជិតៗ/gi;
export const withPlace = (query: string, place: string) =>
  `${query.replace(NEAR_ME, " ").replace(/\s+/g, " ").trim()} near ${place}`;

export const telLink = (phone: string) => `tel:${phone.replace(/[^\d+]/g, "")}`;

/** 45 -> "45 min", 160 -> "2 h 40 min", 120 -> "2 h" (the words come from the UI language). */
export const minutesText = (n: number, t: (key: "minutes" | "hours" | "hoursMinutes", vars: Record<string, number>) => string) =>
  n < 60 ? t("minutes", { n }) : n % 60 === 0 ? t("hours", { h: n / 60 }) : t("hoursMinutes", { h: Math.floor(n / 60), m: n % 60 });

/** Light / Dark / Auto. Auto follows the system, or the user's Telegram theme inside Telegram.
 *  index.html applies the saved theme before the first paint; this keeps it in sync afterwards. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { storage } from "../lib/storage";
import { inTelegram, paintTelegram, setupTelegram } from "../lib/telegram";

export type ThemePref = "light" | "dark" | "auto";
export const THEME_ORDER: ThemePref[] = ["auto", "light", "dark"];

interface Theme {
  pref: ThemePref;
  setPref: (pref: ThemePref) => void;
  /** auto -> light -> dark -> auto (the header button) */
  cycle: () => void;
}

const ThemeContext = createContext<Theme | null>(null);
const darkQuery = matchMedia("(prefers-color-scheme: dark)");

function initialPref(): ThemePref {
  const saved = storage.get("theme");
  return saved === "light" || saved === "dark" || saved === "auto" ? saved : "auto";
}

function apply(pref: ThemePref) {
  const root = document.documentElement;
  if (pref === "auto" && inTelegram) delete root.dataset.theme; // the Telegram theme's colours (tokens.css)
  else root.dataset.theme = pref === "auto" ? (darkQuery.matches ? "dark" : "light") : pref;
  const css = getComputedStyle(root);
  const surface = css.getPropertyValue("--surface").trim();
  const paper = css.getPropertyValue("--paper").trim();
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", surface || paper);
  paintTelegram(!!root.dataset.theme, surface, paper);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [pref, setPrefState] = useState<ThemePref>(initialPref);

  useEffect(() => {
    apply(pref);
    if (pref !== "auto") return;
    const onChange = () => apply("auto");
    darkQuery.addEventListener("change", onChange);
    return () => darkQuery.removeEventListener("change", onChange);
  }, [pref]);

  useEffect(() => {
    setupTelegram(() => apply(initialPref()));
  }, []);

  const setPref = useCallback((next: ThemePref) => {
    setPrefState(next);
    storage.set("theme", next);
  }, []);

  const value = useMemo<Theme>(
    () => ({
      pref,
      setPref,
      cycle: () => setPref(THEME_ORDER[(THEME_ORDER.indexOf(pref) + 1) % THEME_ORDER.length]),
    }),
    [pref, setPref],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): Theme {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside <ThemeProvider>");
  return ctx;
}

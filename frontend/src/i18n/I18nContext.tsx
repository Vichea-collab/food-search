import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { storage } from "../lib/storage";
import { telegramLanguage } from "../lib/telegram";
import { STRINGS, htmlLang, type Lang, type StringKey } from "./strings";

interface I18n {
  lang: Lang;
  setLang: (lang: Lang) => void;
  /** Text for `key`, with {name} placeholders filled from `vars`. */
  t: (key: StringKey, vars?: Record<string, string | number>) => string;
  /** A list of strings (e.g. the suggestion chips). */
  list: (key: StringKey) => readonly string[];
}

const I18nContext = createContext<I18n | null>(null);

function initialLang(): Lang {
  const saved = storage.get("lang");
  if (saved === "en" || saved === "kh") return saved;
  if (saved === "km") return "kh";                       // value saved by an older version
  return /^km/i.test(telegramLanguage() || navigator.language || "") ? "kh" : "en";   // browsers and Telegram say "km"
}

function makeI18n(lang: Lang, setLang: (lang: Lang) => void): I18n {
  const table = STRINGS[lang] as Record<StringKey, unknown>;
  const fallback = STRINGS.en as Record<StringKey, unknown>;
  const raw = (key: StringKey) => table[key] ?? fallback[key];
  return {
    lang,
    setLang,
    t: (key, vars) => {
      let s = String(raw(key));
      if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
      return s;
    },
    list: (key) => (Array.isArray(raw(key)) ? (raw(key) as string[]) : []),
  };
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  useEffect(() => {
    document.documentElement.lang = htmlLang(lang);
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    storage.set("lang", next);
  }, []);

  const value = useMemo<I18n>(() => makeI18n(lang, setLang), [lang, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}

/** The labels under one answer (Map, Call, "Ask next", ...) in the language of that answer, whatever the app's own
 *  language is: a user in the Khmer app who types English gets an English answer, not English text with Khmer buttons. */
export function LangScope({ lang, children }: { lang: Lang | undefined; children: ReactNode }) {
  const outer = useI18n();
  const value = useMemo<I18n>(() => (lang && lang !== outer.lang ? makeI18n(lang, outer.setLang) : outer), [lang, outer]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

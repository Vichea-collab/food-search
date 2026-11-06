/** Telegram Mini App helpers. telegram-web-app.js (index.html) also loads in a normal browser,
 *  where initData is empty, so everything here is a no-op outside Telegram. */

interface TgLocationData {
  latitude: number;
  longitude: number;
}

interface TgLocationManager {
  isInited: boolean;
  isLocationAvailable: boolean;
  isAccessRequested: boolean;
  isAccessGranted: boolean;
  init(callback?: () => void): void;
  getLocation(callback: (data: TgLocationData | null) => void): void;
  openSettings(): void;
}

interface TgBackButton {
  show(): void;
  hide(): void;
  onClick(callback: () => void): void;
  offClick(callback: () => void): void;
}

interface TgWebApp {
  initData: string;
  initDataUnsafe: { user?: { language_code?: string } };
  ready(): void;
  expand(): void;
  isVersionAtLeast(version: string): boolean;
  disableVerticalSwipes?(): void;
  setHeaderColor(color: string): void;
  setBackgroundColor(color: string): void;
  setBottomBarColor?(color: string): void;
  onEvent(event: string, callback: () => void): void;
  openLink(url: string): void;
  BackButton: TgBackButton;
  HapticFeedback?: {
    impactOccurred(style: "light" | "medium" | "heavy"): void;
    notificationOccurred(type: "success" | "error" | "warning"): void;
    selectionChanged(): void;
  };
  LocationManager?: TgLocationManager;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TgWebApp };
  }
}

export const tg: TgWebApp | undefined = window.Telegram?.WebApp;
export const inTelegram = !!(tg && tg.initData);

const safely = (fn: () => void) => {
  try {
    fn();
  } catch {
    /* an older Telegram client without this method */
  }
};

/** Call once at start-up inside Telegram: native look, full height, no swipe-to-close while scrolling the chat. */
export function setupTelegram(onThemeChanged: () => void) {
  if (!inTelegram || !tg) return;
  document.documentElement.classList.add("tg");
  tg.ready();
  tg.expand();
  safely(() => tg.isVersionAtLeast("7.7") && tg.disableVerticalSwipes?.());
  tg.onEvent("themeChanged", onThemeChanged);
}

/** Header/background colours of the Telegram window: our own colours, or the Telegram theme's keywords. */
export function paintTelegram(custom: boolean, surface: string, paper: string) {
  if (!inTelegram || !tg) return;
  const hex = (c: string) => /^#[0-9a-f]{6}$/i.test(c);
  safely(() => {
    tg.setHeaderColor(custom && hex(surface) ? surface : "bg_color");
    tg.setBackgroundColor(custom && hex(paper) ? paper : "secondary_bg_color");
    if (tg.isVersionAtLeast("7.10")) tg.setBottomBarColor?.(custom && hex(paper) ? paper : "secondary_bg_color");
  });
}

export function haptic(kind: "tap" | "select" | "success" | "error") {
  const h = inTelegram ? tg?.HapticFeedback : undefined;
  if (!h) return;
  safely(() => {
    if (kind === "tap") h.impactOccurred("light");
    else if (kind === "select") h.selectionChanged();
    else h.notificationOccurred(kind);
  });
}

/** Telegram opens http links inside its own webview otherwise; send them to the browser / maps app. */
export function openExternal(event: { preventDefault(): void }, url: string) {
  if (!inTelegram || !tg) return;
  event.preventDefault();
  tg.openLink(url);
}

/** Shows Telegram's back button (it calls `callback`); returns a function that hides it again. */
export function showTelegramBack(callback: () => void): () => void {
  if (!inTelegram || !tg) return () => {};
  tg.BackButton.show();
  tg.BackButton.onClick(callback);
  return () => {
    tg.BackButton.offClick(callback);
    tg.BackButton.hide();
  };
}

export function telegramLanguage(): string | undefined {
  return inTelegram ? tg?.initDataUnsafe?.user?.language_code : undefined;
}

import { Avatar } from "../../components/Avatar";
import { Icon, type IconName } from "../../components/Icon";
import { useI18n } from "../../i18n/I18nContext";
import { htmlLang } from "../../i18n/strings";
import { inTelegram } from "../../lib/telegram";
import { useTheme } from "../../theme/ThemeContext";
import type { Status } from "./useChat";

/** "Online", "typing…" or "finding your location…" with a dot (pulses while busy). */
export function StatusLine({ status }: { status: Status }) {
  const { t } = useI18n();
  return (
    <p className={`status${status !== "online" ? " busy" : ""}`}>
      <span className="status-dot" />
      <span>{t(status)}</span>
    </p>
  );
}

/** Bot name and status (opens the profile on phones), theme and language buttons. */
export function ChatHeader({
  status,
  profileOpen,
  onOpenProfile,
}: {
  status: Status;
  profileOpen: boolean;
  onOpenProfile: () => void;
}) {
  const { t, lang, setLang } = useI18n();
  const { pref, cycle } = useTheme();
  const themeName = pref === "auto" && inTelegram ? t("autoTg") : t(pref);
  const themeIcon: IconName = pref === "light" ? "sun" : pref === "dark" ? "moon" : "auto";

  return (
    <header className="bar">
      <button className="who" type="button" aria-controls="profile" aria-expanded={profileOpen} onClick={onOpenProfile}>
        <Avatar size="md" />
        <span className="who-text">
          <span className="who-name" lang={htmlLang(lang)}>{t("appName")}</span>
          <StatusLine status={status} />
        </span>
      </button>
      <div className="bar-actions">
        <button className="icon-btn" type="button" aria-label={t("themeIs", { v: themeName })} title={themeName} onClick={cycle}>
          <Icon name={themeIcon} />
        </button>
        <button
          className="icon-btn lang"
          type="button"
          aria-label="Change language"
          lang={lang === "kh" ? "en" : "km"}
          onClick={() => setLang(lang === "kh" ? "en" : "kh")}
        >
          {lang === "kh" ? "EN" : "ខ្មែរ"}
        </button>
      </div>
    </header>
  );
}

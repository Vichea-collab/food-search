import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { Avatar } from "../../components/Avatar";
import { Icon } from "../../components/Icon";
import { Segmented } from "../../components/Segmented";
import { useI18n } from "../../i18n/I18nContext";
import { htmlLang } from "../../i18n/strings";
import { inTelegram, showTelegramBack } from "../../lib/telegram";
import type { AppConfig, Coords } from "../../lib/types";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { useTheme, type ThemePref } from "../../theme/ThemeContext";
import { StatusLine } from "./ChatHeader";
import type { Status } from "./useChat";

/** The bot's profile: a fixed sidebar on wide screens, a panel that slides in on phones. */
export function ProfilePanel({
  open,
  onClose,
  status,
  config,
  model,
  onModel,
  location,
  onLocationOff,
  recent,
  onAsk,
  onNewChat,
}: {
  open: boolean;
  onClose: () => void;
  status: Status;
  config: AppConfig | null;
  model: string | null;
  onModel: (id: string) => void;
  location: Coords | null;
  onLocationOff: () => void;
  recent: string[];
  onAsk: (q: string) => void;
  onNewChat: () => void;
}) {
  const { t, lang, setLang } = useI18n();
  const { pref, setPref } = useTheme();
  const isSheet = useMediaQuery("(max-width: 1023px)");
  const closeBtn = useRef<HTMLButtonElement>(null);
  const showOpen = isSheet && open;

  // on phones: focus moves in when it opens; Escape and Telegram's back button close it
  useEffect(() => {
    if (!showOpen) return;
    requestAnimationFrame(() => closeBtn.current?.focus());
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const hideBack = showTelegramBack(onClose);
    return () => {
      document.removeEventListener("keydown", onKey);
      hideBack();
    };
  }, [showOpen, onClose]);

  const themeOptions: { value: ThemePref; label: string }[] = [
    { value: "light", label: t("light") },
    { value: "dark", label: t("dark") },
    { value: "auto", label: inTelegram ? t("autoTg") : t("auto") },
  ];

  return (
    <>
      <aside id="profile" className={`profile${showOpen ? " open" : ""}`} aria-labelledby="profileName"
             inert={isSheet && !open ? true : undefined}>
        <div className="profile-top">
          <button ref={closeBtn} className="icon-btn ghost" type="button" aria-label={t("close")} onClick={onClose}>
            <Icon name="back" />
          </button>
        </div>
        <div className="profile-hero">
          <Avatar size="xl" />
          <h2 className="profile-name" id="profileName" lang={htmlLang(lang)}>{t("appName")}</h2>
          <p className="profile-role">{t("role")}</p>
          <StatusLine status={status} />
        </div>

        <div className="profile-actions">
          <button className="act-btn" type="button" onClick={onNewChat}>
            <Icon name="plus" />
            <span>{t("newChat")}</span>
          </button>
          <Link className="act-btn" to="/demo">
            <Icon name="chart" />
            <span>{t("howItWorks")}</span>
          </Link>
        </div>

        <section className="profile-section">
          <h3>{t("about")}</h3>
          <p>{t("aboutText")}</p>
          <ul className="facts-list">
            <li><Icon name="pin" /><span>{config ? t("placesFactN", { n: config.places.toLocaleString() }) : t("placesFact")}</span></li>
            <li><Icon name="translate" /><span>{t("langFact")}</span></li>
            <li><Icon name="list" /><span>{t("sourceFact")}</span></li>
          </ul>
        </section>

        <section className="profile-section">
          <h3 id="themeLabel">{t("appearance")}</h3>
          <Segmented options={themeOptions} value={pref} onChange={setPref} labelledBy="themeLabel" />
          <h3 id="langLabel">{t("language")}</h3>
          <Segmented
            options={[{ value: "en", label: "English", lang: "en" }, { value: "kh", label: "ខ្មែរ", lang: "km" }]}
            value={lang}
            onChange={setLang}
            labelledBy="langLabel"
          />
          {config && config.models.length > 0 && (
            <>
              <h3><label htmlFor="modelSelect">{t("aiModel")}</label></h3>
              <div className="select-wrap">
                <select id="modelSelect" value={model ?? config.default_model} onChange={(e) => onModel(e.target.value)}>
                  {config.models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
                  <option value={config.no_llm}>{t("noAi")}</option>
                </select>
              </div>
              <p className="hint">{t("aiModelHint")}</p>
            </>
          )}
          <h3>{t("location")}</h3>
          <div className="loc-row">
            <p className="loc-state">{t(location ? "locStateOn" : "locStateOff")}</p>
            {location && <button className="link-btn" type="button" onClick={onLocationOff}>{t("turnOff")}</button>}
          </div>
        </section>

        {recent.length > 0 && (
          <section className="profile-section">
            <h3>{t("recent")}</h3>
            <ul className="recent">
              {recent.map((q) => (
                <li key={q}><button type="button" title={q} onClick={() => onAsk(q)}>{q}</button></li>
              ))}
            </ul>
          </section>
        )}

        <p className="profile-foot">
          <span>{t("privacy")}</span>
          <span>{t("osm")}</span>
        </p>
      </aside>
      {showOpen && <div className="scrim" onClick={onClose} />}
    </>
  );
}

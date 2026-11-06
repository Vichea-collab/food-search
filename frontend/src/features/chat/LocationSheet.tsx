import { useEffect, useRef, useState, type FormEvent } from "react";
import { Icon } from "../../components/Icon";
import { useI18n } from "../../i18n/I18nContext";
import { canOpenLocationSettings, getLocation, LocationError, openLocationSettings } from "../../lib/geolocation";
import { haptic, showTelegramBack } from "../../lib/telegram";
import type { Coords } from "../../lib/types";
import type { LocationChoice } from "./useChat";

const POPULAR_HUBS = [
  { name: "Toul Kork", labelKh: "ទួលគោក", labelEn: "Toul Kork" },
  { name: "BKK1", labelKh: "បឹងកេងកង ១", labelEn: "BKK1" },
  { name: "Russian Market", labelKh: "ផ្សារទួលទំពូង", labelEn: "Russian Market" },
  { name: "Riverside", labelKh: "មាត់ទន្លេ", labelEn: "Riverside" },
  { name: "CADT", labelKh: "CADT", labelEn: "CADT" },
];

/** Asks for the location only when a question needs it ("… near me"): Allow, type a place, or Not now.
 *  A native <dialog>: Escape closes it and keyboard focus stays inside while it is open. */
export function LocationSheet({
  open,
  onLocated,
  onDone,
}: {
  open: boolean;
  onLocated: (coords: Coords) => void;
  onDone: (choice: LocationChoice) => void;
}) {
  const { t, lang } = useI18n();
  const dialog = useRef<HTMLDialogElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const placeInput = useRef<HTMLInputElement>(null);
  const [finding, setFinding] = useState(false);
  const [problem, setProblem] = useState<"denied" | "unavailable" | null>(null);
  const [place, setPlace] = useState("");

  useEffect(() => {
    const d = dialog.current;
    if (!d) return;
    if (open && !d.open) {
      setFinding(false);
      setProblem(null);
      setPlace("");
      d.showModal();
      body.current?.focus(); // start at the top, so screen readers read the question first
      return showTelegramBack(() => onDone({ kind: "skip" }));
    }
    if (!open && d.open) d.close();
  }, [open, onDone]);

  const allow = async () => {
    haptic("tap");
    setFinding(true);
    setProblem(null);
    try {
      onLocated(await getLocation());
      haptic("success");
      onDone({ kind: "loc" });
    } catch (err) {
      haptic("error");
      setFinding(false);
      setProblem(err instanceof LocationError ? err.reason : "unavailable");
      placeInput.current?.focus();
    }
  };

  const usePlace = (e: FormEvent) => {
    e.preventDefault();
    const typed = place.trim().slice(0, 60);
    if (typed) onDone({ kind: "place", place: typed });
    else placeInput.current?.focus();
  };

  return (
    <dialog
      ref={dialog}
      className="sheet"
      aria-labelledby="locTitle"
      aria-describedby="locText"
      onCancel={(e) => {
        e.preventDefault(); // Escape
        onDone({ kind: "skip" });
      }}
      onClick={(e) => e.target === dialog.current && onDone({ kind: "skip" })} /* tap outside the card */
    >
      <div className="sheet-body" ref={body} tabIndex={-1}>
        <span className="sheet-icon" aria-hidden="true"><Icon name="pin" /></span>
        <h2 className="sheet-title" id="locTitle">{t("locTitle")}</h2>
        <p className="sheet-text" id="locText">{t("locText")}</p>
        {problem && (
          <p className="sheet-error" role="alert">{t(problem === "denied" ? "locErrDenied" : "locErrUnavailable")}</p>
        )}
        <button className="sheet-primary" type="button" disabled={finding} onClick={allow}>
          {t(finding ? "locFinding" : "locAllow")}
        </button>
        {problem === "denied" && canOpenLocationSettings() && (
          <button className="sheet-settings" type="button" onClick={openLocationSettings}>{t("openSettings")}</button>
        )}
        <form className="sheet-place" onSubmit={usePlace}>
          <label htmlFor="locPlace">{t("locOrType")}</label>
          <div className="sheet-place-row">
            <input
              id="locPlace"
              ref={placeInput}
              type="text"
              maxLength={60}
              autoComplete="off"
              enterKeyHint="search"
              placeholder={t("locPlaceholder")}
              value={place}
              onChange={(e) => setPlace(e.target.value)}
            />
            <button type="submit">{t("locUsePlace")}</button>
          </div>
        </form>
        <div className="sheet-areas">
          <span className="sheet-areas-title">{t("popularAreas")}</span>
          <div className="sheet-chips">
            {POPULAR_HUBS.map((hub) => (
              <button
                key={hub.name}
                type="button"
                className="sheet-chip"
                onClick={() => onDone({ kind: "place", place: hub.name })}
              >
                📍 {lang === "kh" ? hub.labelKh : hub.labelEn}
              </button>
            ))}
          </div>
        </div>
        <button className="sheet-secondary" type="button" onClick={() => onDone({ kind: "skip" })}>{t("locSkip")}</button>
      </div>
    </dialog>
  );
}

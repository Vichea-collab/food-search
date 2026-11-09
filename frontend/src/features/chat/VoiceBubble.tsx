import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { useI18n } from "../../i18n/I18nContext";
import { storage } from "../../lib/storage";

const BARS = 32;
const waves = new Map<string, Promise<{ peaks: number[]; seconds: number }>>();

/** The loudness of a recording in BARS steps (0.12..1) and its length, read once per URL. */
function wave(url: string) {
  let found = waves.get(url);
  if (!found) {
    found = (async () => {
      const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new Ctx();
      try {
        const bytes = await (await fetch(url)).arrayBuffer();
        const audio = await new Promise<AudioBuffer>((resolve, reject) => ctx.decodeAudioData(bytes, resolve, reject));
        const data = audio.getChannelData(0);
        const step = Math.max(1, Math.floor(data.length / BARS));
        const raw = Array.from({ length: BARS }, (_, i) => {
          let peak = 0;
          for (let j = i * step; j < Math.min(data.length, (i + 1) * step); j += 8) peak = Math.max(peak, Math.abs(data[j]));
          return peak;
        });
        const top = Math.max(...raw, 0.01);
        return { peaks: raw.map((p) => Math.max(0.12, p / top)), seconds: audio.duration };
      } finally {
        void ctx.close().catch(() => undefined);
      }
    })();
    waves.set(url, found);
  }
  return found;
}

/** Playback speed, as in Telegram: one tap moves to the next; the choice applies to every voice message and is
 *  remembered on this device. The voice keeps its pitch (the browser's default). */
const RATES = [1, 1.5, 2, 0.5] as const;
const RATE_EVENT = "kn-voice-rate";
const savedRate = (): number => {
  const r = Number(storage.get("voice-rate"));
  return (RATES as readonly number[]).includes(r) ? r : 1;
};
const rateLabel = (r: number) => `${r === 0.5 ? "0.5" : r}×`;

const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** A voice message, as in Telegram: a round play button, the waveform (played part highlighted; tap it to jump),
 *  and the time. `mine` = the user's own recording (the blue bubble). */
export function VoiceBubble({ url, mine = false, autoPlay = false, label, transcript }: {
  url: string | null; mine?: boolean; autoPlay?: boolean; label: string;
  /** the words heard in it: hidden, shown with the "Aa" button (as Telegram's "transcribe") */
  transcript?: string;
}) {
  const { t } = useI18n();
  const audio = useRef<HTMLAudioElement>(null);
  const [peaks, setPeaks] = useState<number[]>(() => Array(BARS).fill(0.25));
  const [seconds, setSeconds] = useState(0);
  const [at, setAt] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(savedRate);
  const [showText, setShowText] = useState(false);

  useEffect(() => {                             // a speed chosen on another voice message applies here too
    const sync = () => setRate(savedRate());
    window.addEventListener(RATE_EVENT, sync);
    return () => window.removeEventListener(RATE_EVENT, sync);
  }, []);
  useEffect(() => {
    if (audio.current) audio.current.playbackRate = rate;
  }, [rate, url]);
  const nextRate = () => {
    const now = savedRate();                    // the saved speed, not this bubble's copy (another tab may have changed it)
    const next = RATES[(RATES.indexOf(now as (typeof RATES)[number]) + 1) % RATES.length];
    storage.set("voice-rate", String(next));
    window.dispatchEvent(new Event(RATE_EVENT));
  };

  useEffect(() => {
    if (!url) return;
    let live = true;
    wave(url).then((w) => {
      if (!live) return;
      setPeaks(w.peaks);
      setSeconds(w.seconds);
    }).catch(() => undefined);                   // no waveform: the flat bars stay, playing still works
    return () => { live = false; };
  }, [url]);

  useEffect(() => {
    if (url && autoPlay) audio.current?.play().catch(() => undefined);   // blocked (e.g. iPhone): the user taps play
  }, [url, autoPlay]);

  const toggle = () => {
    const a = audio.current;
    if (!a || !url) return;
    if (a.paused) void a.play().catch(() => undefined);
    else a.pause();
  };
  const seek = (fraction: number) => {
    const a = audio.current;
    const total = seconds || a?.duration || 0;
    if (!a || !Number.isFinite(total) || !total) return;
    a.currentTime = Math.max(0, Math.min(total, fraction * total));
    setAt(a.currentTime);
  };
  const onBars = (e: PointerEvent<HTMLDivElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    seek((e.clientX - box.left) / box.width);
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const total = seconds || 1;
    if (e.key === "ArrowRight") seek((at + 2) / total);
    else if (e.key === "ArrowLeft") seek((at - 2) / total);
  };

  const done = seconds ? at / seconds : 0;
  return (
    <div className={`voice-bubble bubble${mine ? " mine" : ""}${url ? "" : " loading"}${showText && transcript ? " open" : ""}`}>
      <div className="voice-row">
      {url && (
        <audio ref={audio} src={url} preload="auto"
               onPlay={(e) => { e.currentTarget.playbackRate = rate; setPlaying(true); }} onPause={() => setPlaying(false)}
               onEnded={() => { setPlaying(false); setAt(0); }}
               onTimeUpdate={(e) => setAt(e.currentTarget.currentTime)}
               onLoadedMetadata={(e) => Number.isFinite(e.currentTarget.duration) && !seconds && setSeconds(e.currentTarget.duration)} />
      )}
      <button type="button" className="voice-play" onClick={toggle} disabled={!url}
              aria-label={`${playing ? t("voicePause") : t("voicePlay")}: ${label}`}>
        {!url ? <span className="voice-spin" aria-hidden="true" />
          : playing ? (
            <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="5" width="3.5" height="14" rx="1" /><rect x="13.5" y="5" width="3.5" height="14" rx="1" /></svg>
          ) : (
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5Z" /></svg>
          )}
      </button>
      <div className="voice-main">
        <div className="voice-bars" role="slider" tabIndex={url ? 0 : -1} aria-label={label}
             aria-valuemin={0} aria-valuemax={Math.round(seconds)} aria-valuenow={Math.round(at)}
             aria-valuetext={`${clock(at)} / ${clock(seconds)}`} onPointerDown={onBars} onKeyDown={onKey}>
          {peaks.map((p, i) => (
            <i key={i} className={i / BARS < done ? "on" : undefined} style={{ height: `${Math.round(p * 100)}%` }} />
          ))}
        </div>
        <div className="voice-meta">
          <span className="voice-time">{url ? clock(playing || at ? at : seconds) : t("voiceLoading")}</span>
          <span className="voice-tools">
            {transcript && (
              <button type="button" className="voice-rate" aria-expanded={showText} onClick={() => setShowText((v) => !v)}
                      aria-label={showText ? t("voiceHideText") : t("voiceShowText")}
                      title={showText ? t("voiceHideText") : t("voiceShowText")}>Aa</button>
            )}
            {url && (
              <button type="button" className="voice-rate" onClick={nextRate}
                      aria-label={`${t("voiceSpeed")}: ${rateLabel(rate)}`} title={t("voiceSpeed")}>
                {rateLabel(rate)}
              </button>
            )}
          </span>
        </div>
      </div>
      </div>
      {showText && transcript && <p className="voice-text">{transcript}</p>}
    </div>
  );
}

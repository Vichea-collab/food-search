/** Recording a spoken question in the browser. Chrome records WebM, Safari MP4: neither is reliable for the speech
 *  model, and the server has no audio converter, so the recording is turned into a small 16 kHz mono WAV here
 *  (a minute is about 1.9 MB). Nothing is stored: the recording lives in memory until it is sent. */

export const MAX_RECORD_SECONDS = 60;
const SAMPLE_RATE = 16000;

export class MicDenied extends Error {}

export interface Recording {
  /** Stops and returns the recording as a WAV (null when it was cancelled or empty). */
  stop: () => Promise<Blob | null>;
  /** Stops and throws the recording away. */
  cancel: () => void;
  /** Called with the loudness (0..1) about ten times a second. */
  onLevel: (cb: (level: number) => void) => void;
  /** Called when the maximum length is reached (the recording is then returned by stop()). */
  onLimit: (cb: () => void) => void;
}

export const voiceSupported = (): boolean =>
  typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";

export async function startRecording(): Promise<Recording> {
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  } catch {
    throw new MicDenied();
  }
  const recorder = new MediaRecorder(stream);
  const chunks: Blob[] = [];
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  let cancelled = false;
  let levelCb: ((level: number) => void) | null = null;
  let limitCb: (() => void) | null = null;

  // a rough loudness meter, so the user sees that the microphone hears them
  let meter: number | undefined;
  let audioCtx: AudioContext | undefined;
  try {
    audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    audioCtx.createMediaStreamSource(stream).connect(analyser);
    const data = new Uint8Array(analyser.fftSize);
    meter = window.setInterval(() => {
      analyser.getByteTimeDomainData(data);
      let peak = 0;
      for (const v of data) peak = Math.max(peak, Math.abs(v - 128));
      levelCb?.(Math.min(1, peak / 64));
    }, 100);
  } catch {
    /* no meter: recording still works */
  }

  const release = () => {
    window.clearInterval(meter);
    window.clearTimeout(limit);
    stream.getTracks().forEach((t) => t.stop());
    void audioCtx?.close().catch(() => undefined);
  };
  const limit = window.setTimeout(() => limitCb?.(), MAX_RECORD_SECONDS * 1000);
  const finished = new Promise<void>((resolve) => { recorder.onstop = () => resolve(); });
  recorder.start();

  const halt = () => {
    if (recorder.state !== "inactive") recorder.stop();
    release();
  };

  return {
    onLevel: (cb) => { levelCb = cb; },
    onLimit: (cb) => { limitCb = cb; },
    cancel: () => { cancelled = true; halt(); },
    stop: async () => {
      halt();
      await finished;
      if (cancelled || !chunks.length) return null;
      return toWav(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
    },
  };
}

/** Any recording the browser can play -> 16 kHz mono 16-bit WAV. */
async function toWav(blob: Blob): Promise<Blob | null> {
  const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const ctx = new Ctx();
  try {
    const decoded = await new Promise<AudioBuffer>((resolve, reject) => {
      blob.arrayBuffer().then((bytes) => ctx.decodeAudioData(bytes, resolve, reject), reject);   // callback form: older Safari
    });
    if (decoded.duration < 0.4) return null;                          // a tap, not a question
    const frames = Math.ceil(Math.min(decoded.duration, MAX_RECORD_SECONDS) * SAMPLE_RATE);
    const offline = new OfflineAudioContext(1, frames, SAMPLE_RATE);
    const source = offline.createBufferSource();
    source.buffer = decoded;
    source.connect(offline.destination);
    source.start();
    const samples = (await offline.startRendering()).getChannelData(0);
    return encodeWav(samples);
  } finally {
    void ctx.close().catch(() => undefined);
  }
}

function encodeWav(samples: Float32Array): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const text = (at: number, s: string) => [...s].forEach((c, i) => view.setUint8(at + i, c.charCodeAt(0)));
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVEfmt ");
  view.setUint32(16, 16, true);          // PCM header size
  view.setUint16(20, 1, true);           // PCM
  view.setUint16(22, 1, true);           // mono
  view.setUint32(24, SAMPLE_RATE, true);
  view.setUint32(28, SAMPLE_RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((v, i) => view.setInt16(44 + i * 2, Math.max(-1, Math.min(1, v)) * 0x7fff, true));
  return new Blob([buffer], { type: "audio/wav" });
}

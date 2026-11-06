/** The user's position: Telegram's LocationManager inside the Mini App (Bot API 8.0+), else the browser. */
import type { Coords } from "./types";
import { inTelegram, tg } from "./telegram";

export class LocationError extends Error {
  constructor(public reason: "denied" | "unavailable") {
    super(reason);
  }
}

const telegramLocationSupported = () => inTelegram && !!tg?.LocationManager && tg.isVersionAtLeast("8.0");

function telegramLocation(): Promise<Coords> {
  const lm = tg!.LocationManager!;
  return new Promise((resolve, reject) => {
    const ask = () => {
      if (!lm.isLocationAvailable) return reject(new LocationError("unavailable"));
      lm.getLocation((d) => {
        if (d) resolve({ lat: d.latitude, lng: d.longitude });
        else reject(new LocationError(lm.isAccessRequested && !lm.isAccessGranted ? "denied" : "unavailable"));
      });
    };
    if (lm.isInited) ask();
    else lm.init(ask);
  });
}

function browserLocation(): Promise<Coords> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new LocationError("unavailable"));
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
      (err) => reject(new LocationError(err.code === 1 ? "denied" : "unavailable")),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 },
    );
  });
}

export async function getLocation(): Promise<Coords> {
  if (!telegramLocationSupported()) return browserLocation();
  try {
    return await telegramLocation();
  } catch (err) {
    if (err instanceof LocationError && err.reason === "denied") throw err; // the user said no: don't ask again
    return browserLocation();
  }
}

/** Inside Telegram a blocked location can be re-allowed from the Mini App settings. */
export const canOpenLocationSettings = () => telegramLocationSupported();
export const openLocationSettings = () => tg?.LocationManager?.openSettings();

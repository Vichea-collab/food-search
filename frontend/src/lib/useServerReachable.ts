import { useEffect, useState } from "react";
import { api, ApiError } from "./api";

const CHECK_EVERY_MS = 15_000;

/** True while the backend answers. Asks the server every 15 s (and when the tab comes back or the network
 *  returns); a refused request (e.g. 429) still means the server is up, only no answer / a 5xx means it is down. */
export function useServerReachable(): boolean {
  const [up, setUp] = useState(true);

  useEffect(() => {
    let alive = true;
    const check = () => {
      api
        .config()
        .then(() => alive && setUp(true))
        .catch((e) => alive && setUp(e instanceof ApiError && e.kind === "client"));
    };
    const goOffline = () => setUp(false);
    const onVisible = () => document.visibilityState === "visible" && check();
    const timer = window.setInterval(check, CHECK_EVERY_MS);
    window.addEventListener("online", check);
    window.addEventListener("offline", goOffline);
    document.addEventListener("visibilitychange", onVisible);
    check();
    return () => {
      alive = false;
      window.clearInterval(timer);
      window.removeEventListener("online", check);
      window.removeEventListener("offline", goOffline);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  return up;
}

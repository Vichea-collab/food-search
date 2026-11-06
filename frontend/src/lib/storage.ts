/** localStorage that never throws (private windows, blocked storage). Only small preferences are kept here:
 *  theme, language and AI model. The user's location is never stored. */
export const storage = {
  get(key: string): string | null {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key: string, value: string) {
    try {
      localStorage.setItem(key, value);
    } catch {
      /* storage blocked: the preference lasts until the page closes */
    }
  },
};

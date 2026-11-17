/** "more", "continue", "next", "show me more places", "any more?", "បន្ថែម", "បន្តទៀត": a request for the next places of the
 *  list just shown. The whole message must be this (so "more coffee shops" or "next to CADT" stay searches).
 *  The same pattern as MORE_RE in backend/food_search/llm.py. */
const MORE_RE = new RegExp(
  "^\\s*(?:(?:please|pls|ok|okay|yes|yeah|yep|and)[\\s,]+)*(?:(?:show|give|see|get)\\s+(?:me\\s+)?)?" +
  "(?:(?:some|any)\\s+)?(?:more|next|continue|keep\\s+going|go\\s+on|carry\\s+on)" +
  "(?:\\s+(?:5|five|few|places?|results?|options?|ones?|restaurants?|shops?|page|please|pls|then))*\\s*[?!.]*\\s*$" +
  "|^\\s*(?:សូម\\s*)?(?:បង្ហាញ\\s*)?(?:បន្ថែមទៀត|បន្ថែម|បន្តទៀត|បន្ត|បន្ទាប់ទៀត|បន្ទាប់|ទៀត|មានទៀតទេ|មានទៀតអត់)" +
  "(?:\\s*(?:សូម|ទេ|អត់|ហាង|កន្លែង|លទ្ធផល))*\\s*[?!។.]*\\s*$",
  "i",
);

export const isMoreRequest = (text: string) => MORE_RE.test(text);

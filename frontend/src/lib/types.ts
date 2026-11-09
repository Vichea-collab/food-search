/** The JSON the backend returns (backend/food_search/api). Unknown values are null, never guessed. */

export interface ModelOption {
  id: string;
  label: string;
}

export interface AppConfig {
  photo_search: boolean;
  /** the model that names the dish in a photo ("EfficientNet-B0 (Food-101)" or "CLIP zero-shot"), null if none */
  dish_model?: string | null;
  places: number;
  models: ModelOption[];
  default_model: string;
  no_llm: string;
  /** speaking a question and hearing the answer is switched on */
  voice?: boolean;
}

export interface MenuItem {
  name: string;
  name_en?: string;
  name_kh?: string;
  price_usd: number;
  price_khr?: number;
}

export interface Place {
  id: string;
  name: string;
  dish: string;
  kind: string;
  area: string;
  city?: string;
  price_usd: number | null;
  rating: number | null;
  open_hour: number | null;
  close_hour: number | null;
  open_now: boolean | null;
  distance_km: number | null;
  maps_url: string;
  phone: string | null;
  source: string | null;
  source_url: string | null;
  page_url: string | null;
  page_kind: "facebook" | "website" | null;
  image_url?: string | null;
  menu?: MenuItem[];
  /** the dish asked for, on this place's menu (why it was found): "lok lak" -> Beef Lok Lak $4.00 */
  matched?: { name: string; price_usd: number }[];
  delivery?: { platform: string; url: string }[];
}

export type Origin =
  | { kind: "me" }
  | { kind: "place"; name: string }
  | { kind: "not_found"; name: string }
  | { kind: "no_location" };

export interface Filters {
  max_price?: number;
  min_rating?: number;
  open_now?: boolean;
  open_late?: boolean;
  area?: string;
}

/** One guess of the photo model. */
export interface DishGuess {
  id: string;
  name: string;
  confidence: number;
}

/** The dish in a photo (or picked by the user: confidence null). */
export interface Dish {
  id: string;
  name: string;
  confidence: number | null;
  /** confident enough to say "this looks like …" (otherwise "it might be …" and the other guesses are offered) */
  sure: boolean;
  alternatives: DishGuess[];
  model: string | null;
  has_recipe: boolean;
  /** the photo it was recognised from: sent back when the user corrects the guess, so the app learns it */
  photo_id?: string | null;
  /** the answer came from earlier corrections, not from the model */
  learned?: { users: number; by_you: boolean; similarity: number } | null;
  /** the user just corrected the guess: "saved" (learned) or "expired" (the photo was no longer in memory) */
  corrected?: "saved" | "expired" | null;
}

/** A recipe from data/recipes.csv (Food.com). Times are in minutes. */
export interface Recipe {
  dish_id: string;
  dish_name: string;
  title: string;
  description: string | null;
  prep_minutes: number;
  cook_minutes: number;
  total_minutes: number;
  servings: number | null;
  calories: number | null;
  difficulty: "easy" | "medium" | "hard" | null;
  ingredients: string[];
  steps: string[];
  /** waiting the times may not include: chill, marinate, rise, freeze, rest, soak */
  waiting: string[];
  source: string;
  source_url: string | null;
}

export interface ChatResponse {
  /** search = new places; followup = an answer about places shown before (no new search); chat = small talk;
   *  dish = the dish in a photo (+ recipe + places); recipe = an answer about a dish's recipe */
  kind?: "search" | "followup" | "chat" | "dish" | "recipe";
  query: string;
  /** the search actually run, when it was rebuilt from the conversation ("cheap pizza near me") */
  search_query?: string | null;
  /** followup: the list numbers of the places it is about (as the user saw them) */
  numbers?: number[];
  /** followup: direct = one AI sentence; list / table = built from the data (no AI) */
  shape?: "direct" | "list" | "table";
  lang: "en" | "kh";
  need_location?: boolean;
  answer?: string | null;
  provider?: "gemini" | "ollama" | "cards" | "facts" | "no-results" | "photo" | "correction";
  model?: string | null;
  model_label?: string | null;
  no_match?: string | null;
  /** a condition of the question (under $5, open now) that our data cannot check, said in one sentence */
  unverified_note?: string | null;
  origin?: Origin | null;
  filters?: Filters;
  results?: Place[];
  dish?: Dish;
  recipe?: Recipe | null;
  /** recipe: the part of the recipe the question was about (opened in the card) */
  focus?: "ingredients" | "steps" | null;
  /** follow-up questions to offer as buttons (sent as normal messages, about the dish in focus) */
  suggestions?: string[];
  /** after "no, that's wrong": the photo's guesses to tap (each one corrects photo_id) */
  pick_dishes?: DishGuess[];
  /** "correction": the bot asked for the right answer (a bare /correction, or "no" after a photo): the next message
   *  is sent as "/correction <it>" */
  awaiting?: "correction" | null;
  /** an example of the right answer, shown in the empty box while awaiting */
  hint?: string | null;
  photo_id?: string | null;
  /** earlier corrections of the answer to this same question (the user's own, or checked ones) */
  corrections?: string[];
}

export interface Coords {
  lat: number;
  lng: number;
}

/* ---------- demo ---------- */

export interface DemoSteps {
  text: string;
  filters: string[];
  lang: "en" | "kh";
  matched: number;
  total: number;
  top_k: number;
  method: string;
  geocoded: boolean;
  retrieve_ms: number;
  generate_ms: number;
  prompt_chars: number;
}

export interface ScoredRow {
  name: string;
  dish: string;
  area: string;
  bm25: number;
  embed: number;
  rating_bonus: number;
  distance_bonus: number;
  final: number;
  distance_km: number | null;
}

export interface DemoAskResponse {
  answer: string;
  provider: "gemini" | "ollama" | "cards" | "no-results";
  model_label: string | null;
  chosen_label: string | null;
  fallback: boolean;
  origin: Origin | null;
  steps: DemoSteps;
  rows: ScoredRow[];
  prompt: string;
  weight: number;
}

export interface RankedRow {
  id: string;
  name: string;
  dish: string;
  area: string;
  score: number;
}

export interface CompareResponse {
  text: string;
  filters: string[];
  method: string;
  weight: number;
  bm25: RankedRow[];
  embeddings: RankedRow[];
  hybrid: RankedRow[];
  in_hybrid: string[];
  shared: number;
  hybrid_from_bm25: number;
  hybrid_from_embeddings: number;
  top_k: number;
}

export interface CountRow {
  name: string;
  count: number;
}

export interface DataStats {
  total: number;
  area_count: number;
  with_hours: number;
  with_dish: number;
  coverage: { field: string; count: number }[];
  areas: CountRow[];
  kinds: CountRow[];
  sources: CountRow[];
}

/* ---------- demo: photo -> dish ---------- */

export interface ModelScore {
  model: string;
  top1: number;
  top5: number;
  food101: number;
  khmer: number | null;
  f1: number;
  params_m: number;
  ms: number;
  train_min: number;
}

export interface DemoPhotoResponse {
  model: string | null;
  /** how many dishes the model can tell apart */
  classes: number;
  input: { width: number; height: number; size: number | null; crop: string };
  guesses: (DishGuess & { name_kh: string | null; khmer: boolean })[];
  learned: { users: number; by_you: boolean; similarity: number } | null;
  lead: string;
  classify_ms: number;
  recipe: { title: string; prep_minutes: number; cook_minutes: number; total_minutes: number; servings: number | null;
            source: string; ingredients: number; steps: number } | null;
  search_query: string;
  retrieve_ms: number;
  places: { name: string; dish: string; area: string; matched: { name: string; price_usd: number }[]; maps_url: string }[];
  models: ModelScore[];
}

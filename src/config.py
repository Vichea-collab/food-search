"""Settings and secrets. Values come from environment variables (or .env when run locally)."""
import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)    # does nothing if there is no .env (e.g. in Docker)


def get_secret(name, default=""):
    return (os.getenv(name) or default).strip()


DATA_DIR = ROOT / "data"
EVAL_DIR = DATA_DIR / "eval"
PHOTOS_DIR = DATA_DIR / "photos"
RESULTS_DIR = ROOT / "results"
CHROMA_DIR = ROOT / "chroma_db"
SRC_DIR = ROOT / "src"


# --- secrets & provider settings (values are never printed) ---
TELEGRAM_TOKEN = get_secret("TELEGRAM_TOKEN")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
GEMINI_MODEL = get_secret("GEMINI_MODEL")          # no hardcoded model: set it in .env
OLLAMA_MODEL = get_secret("OLLAMA_MODEL")          # e.g. any model you pulled with `ollama pull`
OLLAMA_HOST = get_secret("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_API_KEY = get_secret("OLLAMA_API_KEY")      # only for Ollama cloud: OLLAMA_HOST=https://ollama.com
LLM_PROVIDER = get_secret("LLM_PROVIDER", "gemini").lower()   # gemini | ollama | none
EMBED_MODEL = get_secret("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
SHEET_CSV_URL = get_secret("SHEET_CSV_URL")          # optional: Google Sheet with the places
SHEET_QUERIES_URL = get_secret("SHEET_QUERIES_URL")  # optional: Google Sheet tab with eval queries
TG_API_ID = get_secret("TG_API_ID")                  # optional: Telegram API (my.telegram.org) for seller channels
TG_API_HASH = get_secret("TG_API_HASH")
ADMIN_IDS = {int(x) for x in re.split(r"[,\s]+", get_secret("ADMIN_IDS")) if x.isdigit()}

# --- search settings ---
TOP_K = 5                 # results shown per query
HYBRID_WEIGHT = 0.5       # 0 = only BM25, 1 = only embeddings
RATING_BOOST = 0.05       # small bonus for well-rated places
DISTANCE_WEIGHT = 0.15    # bonus for nearby places (only when a location is given)
EMBED_CANDIDATES = 5000   # places scored by embeddings per query: all of them for datasets up to this size
MIN_EMBED_SIM = 0.45      # no keyword hit and cosine below this = "not a match" (chosen for MiniLM)
TYPO_CUTOFF = 75          # rapidfuzz score needed to auto-correct a query word
FUZZY_MIN = 0.70          # minimum fuzzy score for the typo fallback
CHEAP_MAX_USD = 3.0       # what "cheap" means
LATE_HOUR = 23            # "open late" = closes at 23:00 or later (or after midnight)
KHR_PER_USD = 4100        # riel per dollar (approximate, change if needed)
TZ = ZoneInfo("Asia/Phnom_Penh")

# --- LLM & bot settings ---
LLM_TIMEOUT_S = 20
OLLAMA_TIMEOUT_S = 60     # local models can be slow on the first call
RATE_LIMIT_PER_MIN = 10
TG_POST_LIMIT = 100       # recent posts read per seller channel

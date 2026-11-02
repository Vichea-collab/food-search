"""Result cards, RAG prompt and LLM providers with fallback (Gemini -> Ollama -> plain cards)."""
import logging

import numpy as np
import pandas as pd
import requests

from .config import *  # noqa: F401,F403
from .search import detect_lang

log = logging.getLogger("food_search.llm")


NO_MATCH = {
    "en": "Sorry, nothing in our list matches that. Try another dish or remove a filter.",
    "km": "សូមអភ័យទោស មិនមានហាងណាត្រូវនឹងការស្វែងរករបស់អ្នកទេ។ សូមសាកល្បងម្ហូបផ្សេង។",
}


def fmt_price(p) -> str:
    return "price unknown" if pd.isna(p) else f"${p:.2f}"


def fmt_hours(open_h, close_h) -> str:
    if pd.isna(open_h) or pd.isna(close_h):
        return "hours unknown"
    return f"{int(open_h):02d}:00–{int(close_h) % 24:02d}:00"


def format_cards(results, lang="en", max_items=TOP_K) -> str:
    """Plain-text result cards (the no-LLM answer)."""
    if results is None or len(results) == 0:
        return NO_MATCH[lang]
    lines = []
    for i, r in enumerate(results.head(max_items).itertuples(), 1):
        dish = r.dish_km if lang == "km" and r.dish_km else r.dish_en
        bits = [fmt_price(r.price_usd), f"⭐ {r.rating:.1f}" if pd.notna(r.rating) else "⭐ n/a",
                r.area, fmt_hours(r.open_hour, r.close_hour)]
        if pd.notna(getattr(r, "distance_km", np.nan)):
            bits.append(f"{r.distance_km:.1f} km away")
        lines.append(f"{i}. {r.name} — {dish}\n   " + " · ".join(bits))
    return "\n".join(lines)


def build_prompt(query, results, lang="en") -> str:
    """The LLM only sees the retrieved rows, so it cannot recommend anything else."""
    rows = []
    for i, r in enumerate(results.head(TOP_K).itertuples(), 1):
        dist = f"{r.distance_km:.1f} km" if pd.notna(getattr(r, "distance_km", np.nan)) else "unknown"
        rows.append(f"{i}. name: {r.name} | dish: {r.dish_en} / {r.dish_km} | price: {fmt_price(r.price_usd)}"
                    f" | rating: {r.rating if pd.notna(r.rating) else 'unknown'} | area: {r.area}"
                    f" | hours: {fmt_hours(r.open_hour, r.close_hour)} | distance: {dist}"
                    f" | notes: {r.description}")
    language = "Khmer" if lang == "km" else "English"
    return (
        "You are a friendly food guide for Phnom Penh, Cambodia.\n"
        "Answer the QUESTION using ONLY the places listed in RESULTS.\n"
        "Rules:\n"
        f"- Answer in {language} (the language of the question).\n"
        "- Recommend at most 3 places, and only places from RESULTS.\n"
        "- Never invent restaurants, prices, opening hours or other facts. If a value is unknown, say so.\n"
        "- If none of the RESULTS fit the question, say clearly that nothing matches.\n"
        "- Keep the answer under 120 words.\n\n"
        f"QUESTION: {query}\n\nRESULTS:\n" + "\n".join(rows)
    )


def safe_error(e) -> str:
    """Short error text with any secret value masked (safe to log)."""
    msg = f"{type(e).__name__}: {e}"[:200]
    for secret in (GEMINI_API_KEY, TELEGRAM_TOKEN, TG_API_HASH, OLLAMA_API_KEY):
        if secret:
            msg = msg.replace(secret, "***")
    return msg


def call_gemini(prompt) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")
    if not GEMINI_MODEL:
        raise RuntimeError("GEMINI_MODEL is not set")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=GEMINI_API_KEY,
                          http_options=types.HttpOptions(timeout=LLM_TIMEOUT_S * 1000))  # milliseconds
    resp = client.models.generate_content(
        model=GEMINI_MODEL, contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=1024))
    text = (resp.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned an empty answer")
    return text


def ollama_headers() -> dict:
    """Ollama cloud needs the API key; it is sent only over HTTPS, never to a plain-http host."""
    if OLLAMA_API_KEY and OLLAMA_HOST.startswith("https://"):
        return {"Authorization": f"Bearer {OLLAMA_API_KEY}"}
    return {}


def call_ollama(prompt) -> str:
    if not OLLAMA_MODEL:
        raise RuntimeError("OLLAMA_MODEL is not set")
    r = requests.post(f"{OLLAMA_HOST}/api/generate", headers=ollama_headers(),
                      json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                            "options": {"temperature": 0.2}},
                      timeout=(5, OLLAMA_TIMEOUT_S))        # (connect, read) seconds
    r.raise_for_status()
    text = r.json().get("response", "").strip()
    if not text:
        raise RuntimeError("Ollama returned an empty answer")
    return text


PROVIDER_CHAINS = {"gemini": ["gemini", "ollama", "cards"],
                   "ollama": ["ollama", "cards"],
                   "none": ["cards"]}


def answer_with_llm(query, results, provider=None):
    """Returns (answer_text, provider_used). Falls back gemini -> ollama -> plain cards."""
    lang = detect_lang(query)
    if results is None or len(results) == 0:
        return NO_MATCH[lang], "no-results"          # nothing retrieved: no LLM call at all
    chain = PROVIDER_CHAINS.get((provider or LLM_PROVIDER).lower())
    if chain is None:
        log.warning("Unknown LLM_PROVIDER %r, using plain cards", provider or LLM_PROVIDER)
        chain = ["cards"]
    prompt = build_prompt(query, results, lang)
    callers = {"gemini": call_gemini, "ollama": call_ollama}
    for name in chain:
        if name == "cards":
            break
        try:
            text = callers[name](prompt)
            log.info("answer provider: %s", name)
            return text, name
        except Exception as e:                       # no key, offline, quota, timeout, ...
            log.warning("%s failed (%s) -> next provider", name, safe_error(e))
    log.info("answer provider: cards")
    return format_cards(results, lang), "cards"


def check_ollama() -> bool:
    """Is Ollama reachable, and is OLLAMA_MODEL available? Prints a hint if not."""
    cloud = OLLAMA_HOST.startswith("https://")
    where = f"Ollama cloud ({OLLAMA_HOST})" if cloud else f"Ollama at {OLLAMA_HOST}"
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", headers=ollama_headers(), timeout=5)
        if r.status_code == 401:
            print(f"❌ {where} rejected the key. Hint: check OLLAMA_API_KEY in .env (create a new one at ollama.com/settings/keys).")
            return False
        r.raise_for_status()
    except Exception:
        hint = "check your internet connection" if cloud else "open the Ollama app (or run: ollama serve)"
        print(f"❌ {where} is not reachable. Hint: {hint}.")
        return False
    names = [m.get("name", "") for m in r.json().get("models", [])]
    print(f"✅ {where} is reachable. Models: " + (", ".join(names[:12]) + (" …" if len(names) > 12 else "") or "none"))
    if not OLLAMA_MODEL:
        print("ℹ️ OLLAMA_MODEL is not set in .env. Choose a model from the list above" + ("." if cloud else ", then run: ollama pull <model>"))
        return False
    if OLLAMA_MODEL not in names and f"{OLLAMA_MODEL}:latest" not in names:
        print(f"❌ Model {OLLAMA_MODEL!r} is not available. Hint: " +
              ("set OLLAMA_MODEL to one of the models listed above." if cloud else f"run: ollama pull {OLLAMA_MODEL}"))
        return False
    print(f"✅ Model {OLLAMA_MODEL!r} is available.")
    return True

"""Search engine: cleaning, BM25 + fuzzy, embeddings + ChromaDB, hybrid ranking, filters."""
import logging
import math
import re
import unicodedata
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import chromadb
import numpy as np
import pandas as pd
import torch
from chromadb.config import Settings
from rank_bm25 import BM25Okapi
from rapidfuzz import fuzz, process

from .config import *  # noqa: F401,F403  (paths + settings)

log = logging.getLogger("food_search")

# Filled by init(): the cleaned table, indexes and models
df = bm25 = BM25_VOCAB = embedder = text_col = image_col = None
HAS_PHOTOS = False


def pick_device() -> str:
    """Prefer an NVIDIA GPU, then Apple Silicon (MPS), then CPU."""
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


DEVICE = pick_device()


KHMER_RE = re.compile(r"[ក-៿᧠-᧿]+")   # Khmer Unicode blocks
WORD_RE = re.compile(r"[a-z0-9]+")
ZERO_WIDTH_RE = re.compile("[\u200b\u2060\ufeff]")      # invisible characters common in Khmer text


def normalize_text(s) -> str:
    """NFC-normalize (important for Khmer), collapse spaces, strip, lowercase."""
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return ""
    s = ZERO_WIDTH_RE.sub("", unicodedata.normalize("NFC", str(s)))
    return re.sub(r"\s+", " ", s).strip().lower()


def detect_lang(text) -> str:
    """'km' if the text contains Khmer script, otherwise 'en'."""
    return "km" if KHMER_RE.search(str(text)) else "en"


def khr_to_usd(amount_khr, rate=None) -> float:
    """Convert Cambodian riel to US dollars."""
    return round(float(amount_khr) / (rate or KHR_PER_USD), 2)


def parse_price(value) -> float:
    """'$2', '2.5', '8000 KHR', '8000៛' -> price in USD. Unknown -> NaN."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return float("nan")
    s = normalize_text(value).replace(",", "")
    num = re.search(r"\d+(?:\.\d+)?", s)
    if not num:
        return float("nan")
    amount = float(num.group())
    if any(unit in s for unit in ("khr", "riel", "៛", "រៀល")):
        return khr_to_usd(amount)
    return amount


ALL_COLUMNS = ["id", "name", "dish_en", "dish_km", "description", "tags", "price_usd",
               "area", "lat", "lng", "rating", "open_hour", "close_hour", "source",
               "source_url", "date", "image_path", "phone_public"]
TEXT_COLS = ["name", "dish_en", "dish_km", "description", "tags", "area",
             "source", "source_url", "date", "image_path", "phone_public"]


def clean_df(raw: pd.DataFrame) -> pd.DataFrame:
    missing = set(ALL_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"restaurants.csv is missing columns: {sorted(missing)}")
    d = raw[ALL_COLUMNS].copy()
    d["id"] = d["id"].fillna("").astype(str).str.strip()
    d = d[~d["id"].isin(["", "id"])]                           # "id" = header row pasted again by a sheet import
    d = d.drop_duplicates("id", keep="first")                    # ids must be unique for ChromaDB
    # text: NFC + single spaces + strip; empty string instead of NaN
    for c in TEXT_COLS:
        d[c] = d[c].fillna("").astype(str).map(
            lambda s: re.sub(r"\s+", " ", ZERO_WIDTH_RE.sub("", unicodedata.normalize("NFC", s))).strip())
    # lowercase the fields we search on (names and areas keep their case for display)
    for c in ["dish_en", "description", "tags"]:
        d[c] = d[c].str.lower()
    d["area_key"] = d["area"].str.lower()
    # numbers: prices may be written in riel; unknown values stay NaN (never guessed)
    d["price_usd"] = d["price_usd"].map(parse_price)
    for c in ["lat", "lng", "rating", "open_hour", "close_hour"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    # one searchable text per row (used by BM25 and by the embedding model)
    d["doc_text"] = (d["name"] + " " + d["dish_en"] + " " + d["dish_km"] + " "
                     + d["description"] + " " + d["tags"].str.replace(";", " ")).map(normalize_text)
    return d


def tokenize(text) -> list:
    """English words (with light plural stemming) + Khmer character 2/3-grams."""
    text = normalize_text(text)
    tokens = [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
              for w in WORD_RE.findall(text)]
    for run in KHMER_RE.findall(text):          # Khmer is written without spaces
        if len(run) < 2:
            tokens.append(run)
        for n in (2, 3):
            tokens += [run[i:i + n] for i in range(len(run) - n + 1)]
    return tokens


def build_bm25(d: pd.DataFrame):
    """BM25 index over the combined text + the English vocabulary (for typo fixing)."""
    corpus = [tokenize(t) for t in d["doc_text"]]
    vocab = sorted({t for doc in corpus for t in doc if WORD_RE.fullmatch(t)})
    return BM25Okapi(corpus), vocab


def correct_tokens(tokens, vocab, cutoff=None):
    """Replace unknown English words by the closest vocabulary word ('carry' -> 'curry')."""
    vocab_set, fixed = set(vocab), []
    for t in tokens:
        if t in vocab_set or len(t) < 4 or not WORD_RE.fullmatch(t):
            fixed.append(t)
            continue
        match = process.extractOne(t, vocab, scorer=fuzz.ratio, score_cutoff=cutoff or TYPO_CUTOFF)
        fixed.append(match[0] if match else t)
    return fixed


def fuzzy_scores(query, d: pd.DataFrame) -> np.ndarray:
    """Typo fallback: fuzzy match the query against names and dish names (spaces removed)."""
    q = normalize_text(query).replace(" ", "")
    fields = (d["name"] + " " + d["dish_en"] + " " + d["dish_km"]).map(normalize_text).str.replace(" ", "")
    scores = np.array([fuzz.partial_ratio(q, f) for f in fields]) / 100
    scores[scores < FUZZY_MIN] = 0.0
    return scores


def bm25_scores(query):
    """Raw BM25 score per row of df (+ which method produced them)."""
    tokens = tokenize(query)
    if not tokens:
        return np.zeros(len(df)), "empty"
    fixed = correct_tokens(tokens, BM25_VOCAB)
    scores = np.asarray(bm25.get_scores(fixed), dtype=float)
    method = "bm25+typo-fix" if fixed != tokens else "bm25"
    if scores.max() <= 0:                    # no keyword hit at all -> fuzzy fallback
        scores, method = fuzzy_scores(query, df), "fuzzy"
    return scores, method


def bm25_search(query, k=TOP_K) -> pd.DataFrame:
    scores, method = bm25_scores(query)
    order = [i for i in np.argsort(-scores, kind="stable") if scores[i] > 0][:k]
    out = df.iloc[order][["id", "name", "dish_en", "dish_km", "price_usd", "area"]].copy()
    out["score"] = scores[order].round(3)
    out["method"] = method
    return out.reset_index(drop=True)


def embed_texts(texts) -> np.ndarray:
    """Unit-length sentence embeddings (so dot product = cosine similarity)."""
    return embedder.encode(list(texts), batch_size=32, normalize_embeddings=True,
                           convert_to_numpy=True, show_progress_bar=False)


@lru_cache(maxsize=2048)
def embed_query(query: str) -> np.ndarray:
    return embed_texts([normalize_text(query)])[0]


def open_chroma():
    return chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))


def get_text_collection(client):
    # one collection per embedding model, so switching EMBED_MODEL never mixes vector sizes
    name = ("food_text_" + re.sub(r"[^a-z0-9]+", "_", EMBED_MODEL.lower()))[:60].strip("_")
    return client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})


def row_metadata(r) -> dict:
    meta = {"name": r["name"], "area": r["area"], "source": r["source"]}
    for c in ["price_usd", "rating", "lat", "lng", "open_hour", "close_hour"]:
        if pd.notna(r[c]):                   # Chroma metadata cannot hold None/NaN
            meta[c] = float(r[c])
    return meta


def build_text_index(d: pd.DataFrame, collection) -> int:
    """Upsert every row (safe to re-run) and delete ids that are no longer in the CSV."""
    collection.upsert(ids=d["id"].tolist(),
                      embeddings=embed_texts(d["doc_text"]).tolist(),
                      documents=d["doc_text"].tolist(),
                      metadatas=[row_metadata(r) for _, r in d.iterrows()])
    stale = set(collection.get(include=[])["ids"]) - set(d["id"])
    if stale:
        collection.delete(ids=sorted(stale))
    return collection.count()


def embedding_scores(query) -> np.ndarray:
    """Cosine similarity per row of df (rows beyond EMBED_CANDIDATES, if any, get 0)."""
    n = min(EMBED_CANDIDATES, text_col.count())
    res = text_col.query(query_embeddings=[embed_query(query).tolist()], n_results=n,
                         include=["distances"])
    sims = {i: 1.0 - dist for i, dist in zip(res["ids"][0], res["distances"][0])}
    return np.array([sims.get(i, 0.0) for i in df["id"]])


def embedding_search(query, k=TOP_K) -> pd.DataFrame:
    scores = embedding_scores(query)
    order = np.argsort(-scores, kind="stable")[:k]
    out = df.iloc[order][["id", "name", "dish_en", "dish_km", "price_usd", "area"]].copy()
    out["score"] = scores[order].round(3)
    return out.reset_index(drop=True)


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance in km (works on numbers or numpy/pandas arrays)."""
    lat1, lng1, lat2, lng2 = (np.radians(np.asarray(x, dtype=float)) for x in (lat1, lng1, lat2, lng2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def minmax(x) -> np.ndarray:
    """Scale to 0..1 so BM25 and cosine scores become comparable."""
    x = np.asarray(x, dtype=float)
    lo, hi = x.min(), x.max()
    return np.zeros_like(x) if hi - lo < 1e-12 else (x - lo) / (hi - lo)


PRICE_RE = re.compile(r"(?:under|below|less than|cheaper than|max|<|ក្រោម|តិចជាង)\s*\$?\s*(\d+(?:\.\d+)?)"
                      r"\s*(\$|usd|dollars?|ដុល្លារ|khr|riel|៛|រៀល)?")
FILTER_PHRASES = [  # (regex, filter name, value)
    (r"\bopen (?:right )?now\b|បើកឥឡូវ", "open_now", True),
    (r"\bopen late\b|\blate night\b|\blate\b|បើកយប់|យប់ជ្រៅ", "open_late", True),
    (r"\bcheap\b|\bbudget\b|ថោក", "max_price", CHEAP_MAX_USD),
    (r"\btop rated\b|\bbest rated\b", "min_rating", 4.5),
]


def parse_query_filters(query):
    """Pull conditions out of the query text. Returns (remaining query, filters dict)."""
    q, f = normalize_text(query), {}
    m = PRICE_RE.search(q)
    if m:
        amount, unit = float(m.group(1)), (m.group(2) or "$")
        f["max_price"] = khr_to_usd(amount) if unit in ("khr", "riel", "៛", "រៀល") else amount
        q = q.replace(m.group(0), " ")
    for pattern, key, value in FILTER_PHRASES:
        if re.search(pattern, q):
            f.setdefault(key, value)
            q = re.sub(pattern, " ", q)
    for area in sorted(df["area_key"].unique(), key=len, reverse=True):
        if area and area in q:
            f["area"] = area
            q = q.replace(area, " ")
            break
    return re.sub(r"\s+", " ", q).strip(), f


def is_open_at(open_h, close_h, hour) -> bool:
    """Opening hours may cross midnight (e.g. 18 -> 2). Unknown hours = not open."""
    if pd.isna(open_h) or pd.isna(close_h):
        return False
    open_h, close_h = float(open_h), float(close_h) % 24
    if open_h == close_h:
        return True                          # open 24 hours
    if open_h < close_h:
        return open_h <= hour < close_h
    return hour >= open_h or hour < close_h


def closes_late(open_h, close_h) -> bool:
    if pd.isna(open_h) or pd.isna(close_h):
        return False
    return close_h >= LATE_HOUR or close_h < open_h


def apply_filters(d: pd.DataFrame, f: dict, now=None) -> np.ndarray:
    """Boolean mask. Rows with an unknown price never pass a price filter."""
    mask = np.ones(len(d), dtype=bool)
    if f.get("max_price") is not None:
        mask &= d["price_usd"].le(f["max_price"]).to_numpy()
    if f.get("min_rating") is not None:
        mask &= d["rating"].ge(f["min_rating"]).to_numpy()
    if f.get("area"):
        mask &= d["area_key"].eq(normalize_text(f["area"])).to_numpy()
    if f.get("open_now"):
        now = now or datetime.now(TZ)
        hour = now.hour + now.minute / 60
        mask &= np.array([is_open_at(o, c, hour) for o, c in zip(d["open_hour"], d["close_hour"])], dtype=bool)
    if f.get("open_late"):
        mask &= np.array([closes_late(o, c) for o, c in zip(d["open_hour"], d["close_hour"])], dtype=bool)
    return mask


def hybrid_search(query, k=TOP_K, user_loc=None, weight=None, filters=None,
                  use_query_filters=True, now=None) -> pd.DataFrame:
    """BM25 + embeddings + rating + distance, after filters. user_loc = (lat, lng)."""
    weight = HYBRID_WEIGHT if weight is None else weight
    text, parsed = parse_query_filters(query) if use_query_filters else (normalize_text(query), {})
    flt = {**parsed, **(filters or {})}
    out = df.copy()
    if text:
        bm, method = bm25_scores(text)
        em = embedding_scores(text)
    else:                                    # query was only conditions, e.g. "open now"
        bm, em, method = np.zeros(len(df)), np.zeros(len(df)), "filters-only"
    out["bm25"], out["embed"] = minmax(bm), minmax(em)
    out["rating_boost"] = RATING_BOOST * out["rating"].fillna(0) / 5
    out["distance_km"], out["distance"] = np.nan, 0.0
    if user_loc:
        out["distance_km"] = haversine_km(user_loc[0], user_loc[1], out["lat"], out["lng"])
        out["distance"] = DISTANCE_WEIGHT / (1 + out["distance_km"].fillna(1e6))
    out["final"] = weight * out["embed"] + (1 - weight) * out["bm25"] + out["rating_boost"] + out["distance"]
    keep = apply_filters(out, flt, now)
    if text:                                 # drop rows that match neither by keyword nor by meaning
        keep &= (bm > 0) | (em >= MIN_EMBED_SIM)
    out = out[keep].sort_values("final", ascending=False, kind="stable").head(k).reset_index(drop=True)
    out.attrs.update(filters=flt, method=method, query_text=text)
    return out


def get_rows(ids) -> pd.DataFrame:
    """Rows for the given ids, in that order (unknown ids are skipped)."""
    known = set(df["id"])
    ids = [i for i in dict.fromkeys(ids) if i in known]
    return df.set_index("id").loc[ids].reset_index()


CLIP_ARCH, CLIP_PRETRAINED = "ViT-B-32", "laion2b_s34b_b79k"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_clip = {}          # model, preprocess, tokenizer (loaded on first use)


def list_photos(folder=None) -> list:
    folder = Path(folder or PHOTOS_DIR)
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_EXTS) if folder.exists() else []


def load_clip():
    if not _clip:
        import open_clip
        model, _, preprocess = open_clip.create_model_and_transforms(
            CLIP_ARCH, pretrained=CLIP_PRETRAINED, device=DEVICE)
        model.eval()
        _clip.update(model=model, preprocess=preprocess, tokenizer=open_clip.get_tokenizer(CLIP_ARCH))
    return _clip["model"], _clip["preprocess"], _clip["tokenizer"]


@torch.no_grad()
def clip_embed_images(paths) -> np.ndarray:
    from PIL import Image
    model, preprocess, _ = load_clip()
    batch = torch.stack([preprocess(Image.open(p).convert("RGB")) for p in paths]).to(DEVICE)
    feats = model.encode_image(batch)
    return (feats / feats.norm(dim=-1, keepdim=True)).float().cpu().numpy()


@torch.no_grad()
def clip_embed_text(texts) -> np.ndarray:
    model, _, tokenizer = load_clip()
    feats = model.encode_text(tokenizer(list(texts)).to(DEVICE))
    return (feats / feats.norm(dim=-1, keepdim=True)).float().cpu().numpy()


def get_image_collection(client):
    return client.get_or_create_collection("food_images_" + CLIP_ARCH.lower().replace("-", "_"),
                                           metadata={"hnsw:space": "cosine"})


def build_image_index(paths, collection, d: pd.DataFrame) -> int:
    """Photo -> restaurant id: by image_path file name, else by file stem (<id>.jpg -> <id>)."""
    by_name = {Path(p).name: i for i, p in zip(d["id"], d["image_path"]) if p}
    ids = [p.relative_to(PHOTOS_DIR).as_posix() for p in paths]
    embs = np.vstack([clip_embed_images(paths[i:i + 16]) for i in range(0, len(paths), 16)])
    collection.upsert(ids=ids, embeddings=embs.tolist(),
                      metadatas=[{"path": p.relative_to(ROOT).as_posix(),
                                  "restaurant_id": by_name.get(p.name, p.stem)} for p in paths])
    stale = set(collection.get(include=[])["ids"]) - set(ids)
    if stale:
        collection.delete(ids=sorted(stale))
    return collection.count()


def _image_query(emb, k):
    res = image_col.query(query_embeddings=[emb.tolist()], n_results=min(k, image_col.count()),
                          include=["metadatas", "distances"])
    return [{"path": ROOT / m["path"], "restaurant_id": m["restaurant_id"], "similarity": round(1 - dist, 3)}
            for m, dist in zip(res["metadatas"][0], res["distances"][0])]


def search_images_by_text(query, k=TOP_K):
    return _image_query(clip_embed_text([query])[0], k)


def search_images_by_image(path, k=TOP_K):
    return _image_query(clip_embed_images([path])[0], k)


def image_search_available() -> bool:
    return bool(HAS_PHOTOS) and image_col is not None


def init():
    """Load data/restaurants.csv and build (or refresh) every index. Call once at startup."""
    global df, bm25, BM25_VOCAB, embedder, text_col, image_col, HAS_PHOTOS
    from sentence_transformers import SentenceTransformer
    df = clean_df(pd.read_csv(DATA_DIR / "restaurants.csv", dtype={"id": str, "phone_public": str, "price_usd": str}))
    bm25, BM25_VOCAB = build_bm25(df)
    embedder = SentenceTransformer(EMBED_MODEL, device=DEVICE)
    client = open_chroma()
    text_col = get_text_collection(client)
    build_text_index(df, text_col)
    photos = list_photos()
    HAS_PHOTOS = bool(photos)
    if HAS_PHOTOS:
        image_col = get_image_collection(client)
        build_image_index(photos, image_col, df)
    log.info("search ready: %d places, %d photos, device=%s", len(df), len(photos), DEVICE)

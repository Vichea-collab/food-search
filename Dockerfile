# Slim image for the Telegram bot.   Build: docker build -t food-bot .
# Run (secrets come from the host, never from the image):  docker run --env-file .env food-bot
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/app/.cache/huggingface
WORKDIR /app

# CPU-only torch keeps the image small (the default Linux wheel bundles CUDA, several GB)
COPY requirements.txt .
RUN pip install --no-cache-dir torch==$(grep '^torch==' requirements.txt | cut -d= -f3) \
        --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

# Cache the embedding model in an image layer so containers start fast and work offline.
# Change EMBED_MODEL here AND at runtime if you switch models (e.g. BAAI/bge-m3).
ARG EMBED_MODEL=paraphrase-multilingual-MiniLM-L12-v2
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBED_MODEL}')"

COPY src/ src/
COPY bot.py .
COPY data/ data/
# Prebuilt vector index from the notebook (init() only refreshes it)
COPY chroma_db/ chroma_db/

CMD ["python", "bot.py"]

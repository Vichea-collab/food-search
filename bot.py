"""Cambodian food search Telegram bot.

Run:  python bot.py      (TELEGRAM_TOKEN etc. come from the environment or a local .env)

Switch to a webhook (e.g. Cloud Run / a VPS with HTTPS) by replacing app.run_polling(...) with:
    app.run_webhook(listen="0.0.0.0", port=int(os.environ.get("PORT", 8080)),
                    url_path="telegram", webhook_url="https://YOUR-DOMAIN/telegram",
                    secret_token=os.environ["WEBHOOK_SECRET"])
(this needs: pip install "python-telegram-bot[webhooks]")
"""
import logging
import sys

from src import search
from src.bot_handlers import build_bot_app
from src.config import TELEGRAM_TOKEN


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)   # httpx logs URLs that contain the token
    if not TELEGRAM_TOKEN:
        sys.exit("TELEGRAM_TOKEN is not set (environment variable or .env).")
    search.init()
    app = build_bot_app(TELEGRAM_TOKEN)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

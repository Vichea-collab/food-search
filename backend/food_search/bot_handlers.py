"""Telegram bot (python-telegram-bot v20+): formatter, handlers and app builder."""
import asyncio
import html
import logging
import os
import tempfile
import time
from collections import Counter, defaultdict, deque
from pathlib import Path
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler
from telegram.ext import filters as tg_filters

from .config import ADMIN_IDS, RATE_LIMIT_PER_MIN, TOP_K
from .llm import NO_MATCH, answer_with_llm, fmt_price, safe_error
from .search import detect_lang, get_rows, hybrid_search, image_search_available, search_images_by_image

log = logging.getLogger("food_search.bot")


def maps_url(lat, lng, name="") -> str:
    if pd.isna(lat) or pd.isna(lng):
        return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(f"{name} Phnom Penh")
    return f"https://www.google.com/maps/search/?api=1&query={lat:.6f},{lng:.6f}"


def format_telegram(results, lang="en", start=0, max_items=5) -> str:
    """Telegram HTML message: up to 5 results with price, rating, distance and a Maps link."""
    if results is None or len(results) == 0:
        return html.escape(NO_MATCH[lang])
    blocks = []
    for i, r in enumerate(results.iloc[start:start + max_items].itertuples(), start + 1):
        dish = r.dish_km if lang == "km" and r.dish_km else r.dish_en
        bits = [fmt_price(r.price_usd), f"⭐ {r.rating:.1f}" if pd.notna(r.rating) else "⭐ n/a", r.area]
        if pd.notna(getattr(r, "distance_km", np.nan)):
            bits.append(f"📏 {r.distance_km:.1f} km")
        url = html.escape(maps_url(r.lat, r.lng, r.name), quote=True)
        blocks.append(f"<b>{i}. {html.escape(r.name)}</b> — {html.escape(dish)}\n"
                      f"{html.escape(' · '.join(bits))}\n<a href=\"{url}\">📍 Google Maps</a>")
    return "\n\n".join(blocks)


HELP_TEXT = (
    "🍜 Cambodian food search bot\n"
    "Send a dish name, e.g. 'curry noodle', 'kuy teav open now', 'bbq under $5'.\n"
    "Share your 📍 location to get distances, or send a 📷 food photo.\n"
    "/privacy – how your data is used · /deleteme – forget my location\n"
    "Place data: © OpenStreetMap contributors (ODbL)\n\n"
    "🍜 បូតស្វែងរកម្ហូបខ្មែរ\n"
    "សូមផ្ញើឈ្មោះម្ហូប ឧ. 'នំបញ្ចុក', 'គុយទាវ ថោក'។\n"
    "ចែករំលែក 📍 ទីតាំង ដើម្បីដឹងចម្ងាយ ឬផ្ញើ 📷 រូបម្ហូប។"
)
PRIVACY_TEXT = (
    "🔒 No account needed. Your location and photos are used only to answer your request "
    "and are not stored: your location stays in memory until /deleteme or a bot restart, "
    "photos are deleted right after the search.\n\n"
    "🔒 មិនចាំបាច់មានគណនីទេ។ ទីតាំង និងរូបថតរបស់អ្នក ប្រើតែដើម្បីឆ្លើយតបប៉ុណ្ណោះ ហើយមិនត្រូវបានរក្សាទុកទេ។"
)
RATE_LIMIT_TEXT = "⏳ Too many requests – please wait a minute. / សូមរង់ចាំមួយនាទី។"

STATS = Counter()           # in-memory counters for /stats (no message text, no ids)
_seen_users = set()
_user_hits = defaultdict(deque)


def allow_request(user_id, now=None) -> bool:
    """Sliding-window rate limit: RATE_LIMIT_PER_MIN requests per user per 60 s."""
    now = time.monotonic() if now is None else now
    hits = _user_hits[user_id]
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= RATE_LIMIT_PER_MIN:
        return False
    hits.append(now)
    return True


async def _guard(update, kind) -> bool:
    """Count the request and enforce the rate limit."""
    uid = update.effective_user.id
    _seen_users.add(uid)
    STATS[kind] += 1
    if not allow_request(uid):
        STATS["rate_limited"] += 1
        await update.effective_message.reply_text(RATE_LIMIT_TEXT)
        return False
    return True


def results_keyboard(results, start=0, max_items=5):
    """'Open in Maps' URL buttons for the first 3 shown results + a 'More results' button."""
    rows = [[InlineKeyboardButton(f"📍 Open in Maps: {r.name[:28]}", url=maps_url(r.lat, r.lng, r.name))]
            for r in results.iloc[start:start + 3].itertuples()]
    if len(results) > start + max_items:
        rows.append([InlineKeyboardButton("➕ More results", callback_data="more")])
    return InlineKeyboardMarkup(rows) if rows else None


async def start_cmd(update, context):
    await update.message.reply_text(HELP_TEXT)


async def privacy_cmd(update, context):
    await update.message.reply_text(PRIVACY_TEXT)


async def deleteme_cmd(update, context):
    context.user_data.clear()                # location + last results
    await update.message.reply_text("🗑️ Your saved location was deleted. / ទីតាំងរបស់អ្នកត្រូវបានលុប។")


async def stats_cmd(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admins only.")
        return
    lines = [f"{k}: {v}" for k, v in sorted(STATS.items())] + [f"unique users: {len(_seen_users)}"]
    await update.message.reply_text("📊 Bot stats (since start)\n" + "\n".join(lines))


async def send_results(message, context, results, lang, intro=""):
    context.user_data.update(last_results=results, last_lang=lang, offset=0)
    text = (intro + "\n\n" if intro else "") + format_telegram(results, lang)
    await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=results_keyboard(results),
                             link_preview_options=LinkPreviewOptions(is_disabled=True))


async def text_handler(update, context):
    if not await _guard(update, "text_queries"):
        return
    query = update.message.text.strip()[:200]
    lang = detect_lang(query)
    log.info("text query (lang=%s, %d chars)", lang, len(query))   # never log text together with ids
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    results = await asyncio.to_thread(hybrid_search, query, 15, context.user_data.get("location"))
    answer, provider = await asyncio.to_thread(answer_with_llm, query, results.head(TOP_K))
    intro = html.escape(answer) if provider in ("gemini", "ollama") else ""
    await send_results(update.message, context, results, lang, intro)


async def more_callback(update, context):
    q = update.callback_query
    await q.answer()
    results, lang = context.user_data.get("last_results"), context.user_data.get("last_lang", "en")
    offset = context.user_data.get("offset", 0) + 5
    if results is None or offset >= len(results):
        await q.message.reply_text("No more results. / មិនមានលទ្ធផលទៀតទេ។")
        return
    context.user_data["offset"] = offset
    await q.message.reply_text(format_telegram(results, lang, start=offset), parse_mode=ParseMode.HTML,
                               reply_markup=results_keyboard(results, start=offset),
                               link_preview_options=LinkPreviewOptions(is_disabled=True))


async def location_handler(update, context):
    if not await _guard(update, "locations"):
        return
    loc = update.message.location
    context.user_data["location"] = (loc.latitude, loc.longitude)   # memory only
    await update.message.reply_text(
        "📍 Location saved for this chat (in memory only). Now send a dish name. /deleteme to forget it.\n"
        "📍 បានរក្សាទីតាំងបណ្ដោះអាសន្ន។ សូមផ្ញើឈ្មោះម្ហូប។")


async def photo_handler(update, context):
    if not await _guard(update, "photo_queries"):
        return
    if not image_search_available():
        await update.message.reply_text("📷 Photo search is not set up yet. Please type the dish name instead.")
        return
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    tg_file = await update.message.photo[-1].get_file()
    fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        await tg_file.download_to_drive(tmp_path)
        matches = await asyncio.to_thread(search_images_by_image, tmp_path, 10)
    finally:
        Path(tmp_path).unlink(missing_ok=True)   # the user's photo is never kept
    results = get_rows([m["restaurant_id"] for m in matches])
    await send_results(update.message, context, results, "en", "📷 Places with similar-looking food:")


async def error_handler(update, context):
    log.error("bot error: %s", safe_error(context.error))


def build_bot_app(token):
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler(["start", "help"], start_cmd))
    app.add_handler(CommandHandler("privacy", privacy_cmd))
    app.add_handler(CommandHandler("deleteme", deleteme_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CallbackQueryHandler(more_callback, pattern="^more$"))
    app.add_handler(MessageHandler(tg_filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(tg_filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(tg_filters.TEXT & ~tg_filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)
    return app

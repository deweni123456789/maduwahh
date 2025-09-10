# modules/pexels.py
import os
import aiohttp
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

PEXELS_API_KEY = os.getenv(
    "PEXELS_API_KEY",
    "veZI7AhoLrQwUFCMk6aHiJjznoi3Q1bu0d6L5cpFQMTkZNYJXQqtDTnZ"
)

async def wallpaper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch a wallpaper from Pexels based on a search query."""
    if not context.args:
        await update.message.reply_text(
            "📷 Please provide a wallpaper name.\nExample: `/wallpaper nature`",
            parse_mode="Markdown"
        )
        return

    query = " ".join(context.args)
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"Authorization": PEXELS_API_KEY}) as resp:
                data = await resp.json()

        if not data.get("photos"):
            await update.message.reply_text("❌ No wallpapers found for your query.")
            return

        photo_url = data["photos"][0]["src"]["original"]
        caption = f"📷 Wallpaper: <b>{query}</b>"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👨‍💻 Contact Developer", url="https://t.me/deweni2")]
        ])

        await update.message.reply_photo(
            photo=photo_url,
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logging.error(f"Wallpaper error: {e}")
        await update.message.reply_text("⚠️ Error fetching wallpaper. Please try again later.")

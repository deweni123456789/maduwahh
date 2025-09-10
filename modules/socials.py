import asyncio
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .downloader import download_video

# Path to cookies file for Instagram
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")

async def handle_social(update: Update, context: ContextTypes.DEFAULT_TYPE, platform: str):
    if not context.args:
        await update.message.reply_text(f"Usage: /{platform} <url>")
        return

    url = context.args[0]
    msg = await update.message.reply_text(f"⬇ Downloading from {platform}...")

    try:
        # If Instagram, use cookies.txt
        cookies_path = None
        if platform == "insta" and os.path.exists(COOKIES_FILE):
            cookies_path = COOKIES_FILE

        path, info = await asyncio.get_event_loop().run_in_executor(
            None, download_video, url, cookies_path, False
        )

        title = info.get("title", f"{platform.capitalize()} Video")
        requester = update.effective_user.mention_html()

        caption = (
            f"📹 <b>{title}</b>\n"
            f"🙋‍♂️ Requested by: {requester}"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/deweni2")]
        ])

        await update.message.reply_document(
            open(path, "rb"),
            caption=caption,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ Failed: {e}")

async def handle_fb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_social(update, context, "fb")

async def handle_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_social(update, context, "tiktok")

async def handle_insta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_social(update, context, "insta")

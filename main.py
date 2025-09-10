import os
import logging
import asyncio
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
)

from modules.song import register
from modules.video import handle_video
from modules.pexels import wallpaper
from modules.socials import handle_fb, handle_tiktok, handle_insta
from modules import downloader
from modules import adult_downloader
from modules.image_gen import get_image_handler
from modules import broadcast
from modules.lyrics import add_lyrics_handler  # ✅ Lyrics module import
from modules.find import find_music  # Song finder

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7896090354:AAFPlTN5x413nHnmaIRT4WS68fYiG31kR6Q")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "veZI7AhoLrQwUFCMk6aHiJjznoi3Q1bu0d6L5cpFQMTkZNYJXQqtDTnZ")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# -----------------------
# Start Command
# -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_text = (
        "Hello DeWeNi🇱🇰!\n\n"
        "I'm <b>𝙀𝙇𝙄𝙕𝘼 🍭</b>, your new media companion.\n\n"
        "🎧 Ready to dive into some social media downloads?\n"
        "➜ I'm a powerful and efficient Telegram downloader bot with some amazing features. "
        "Let’s make your day melodious!"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 Add Me to Your Group", url=f"https://t.me/{context.bot.username}?startgroup=true")],
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/deweni2")],
        [InlineKeyboardButton("📢 Support Channel", url="https://t.me/slmusicmania")]
    ])

    await update.message.reply_photo(
        photo="https://telegra.ph/file/ee7d75a552dd22796807f.jpg",
        caption=start_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

# -----------------------
# Wallpaper Command
# -----------------------
async def wallpaper_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "📷 Please provide a wallpaper name.\nExample: /wallpaper nature",
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

                await update.message.reply_photo(photo=photo_url, caption=caption, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        logging.error(f"Wallpaper error: {e}")
        await update.message.reply_text("⚠️ Error fetching wallpaper. Please try again later.")

# -----------------------
# Adult Download Command (Private only)
# -----------------------
async def adult_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        await update.message.reply_text("❌ This command works only in private chat.")
        return

    if not context.args:
        await update.message.reply_text("🔞 Please provide a valid adult video link.")
        return

    url = context.args[0]
    await adult_downloader.download_adult(update, context, url)

# -----------------------
# Auto delete service messages
# -----------------------
async def delete_service_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.delete()
    except Exception:
        pass

# -----------------------
# Error handler
# -----------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, asyncio.TimeoutError):
        return
    if "Timed out" in str(err) or "Cancelled" in str(err):
        return
    logging.error(f"Error: {err}")

# -----------------------
# Main Function
# -----------------------
def main():
    if BOT_TOKEN in ("REPLACE_WITH_YOUR_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE", "YOUR_TELEGRAM_BOT_TOKEN"):
        print("❌ Please set TELEGRAM_BOT_TOKEN environment variable or edit main.py with your token.")
        return

    app = ApplicationBuilder() \
        .token(BOT_TOKEN) \
        .read_timeout(300) \
        .write_timeout(300) \
        .connect_timeout(60) \
        .build()

    # Pass running loop to downloader if needed
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    downloader.set_main_loop(loop)

    # -----------------------
    # Commands
    # -----------------------
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("song", register))
    app.add_handler(CommandHandler("video", handle_video))
    app.add_handler(CommandHandler("fb", handle_fb))
    app.add_handler(CommandHandler("tiktok", handle_tiktok))
    app.add_handler(CommandHandler("insta", handle_insta))
    app.add_handler(CommandHandler("find", find_music))
    app.add_handler(CommandHandler("wallpaper", wallpaper_cmd))
    app.add_handler(CommandHandler("adult", adult_cmd))
    app.add_handler(CommandHandler("image", get_image_handler))

    # -----------------------
    # Add Lyrics Command
    # -----------------------
    add_lyrics_handler(app)

    app.add_handler(MessageHandler(
        filters.AUDIO | filters.VOICE | filters.VIDEO | filters.VIDEO_NOTE,
        find_music
    ))

    # -----------------------
    # Broadcast module handlers
    # -----------------------
    for handler in broadcast.get_handlers():
        app.add_handler(handler)

    # -----------------------
    # Track chats on any message
    # -----------------------
    app.add_handler(MessageHandler(filters.ALL, broadcast.track_chat))

    # -----------------------
    # Delete service messages
    # -----------------------
    app.add_handler(MessageHandler(filters.StatusUpdate.ALL, delete_service_messages))

    # -----------------------
    # Error handler
    # -----------------------
    app.add_error_handler(error_handler)

    print("✅ Bot is running...")
    app.run_polling()

# -----------------------
# Run main
# -----------------------
if __name__ == "__main__":
    main()

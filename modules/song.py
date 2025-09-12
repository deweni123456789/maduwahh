import os
import yt_dlp
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import shutil

MAIN_LOOP = None

def set_main_loop(loop):
    global MAIN_LOOP
    MAIN_LOOP = loop

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        msg = await update.message.reply_text("Usage: /song <YouTube URL or keywords>")
        await asyncio.sleep(8)
        await msg.delete()
        return

    query = " ".join(context.args)

    # URL check / fallback to search
    if query.startswith("http://") or query.startswith("https://"):
        url = query
    else:
        url = f"ytsearch1:{query}"

    status_msg = await update.message.reply_text("🎵 Downloading audio, please wait...")

    os.makedirs("downloads", exist_ok=True)

    # FFmpeg check
    if not shutil.which("ffmpeg"):
        await status_msg.edit_text(
            "❌ FFmpeg is not installed or not in PATH.\n"
            "➡️ Please install FFmpeg from https://ffmpeg.org/download.html"
        )
        await asyncio.sleep(8)
        await status_msg.delete()
        return

    # cookies.txt check
    cookie_path = "modules/cookies.txt"
    if not os.path.exists(cookie_path):
        cookie_path = None

    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": False,
        "noplaylist": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["web"]  # force only web client
            }
        }
    }

    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path

    loop = MAIN_LOOP or asyncio.get_event_loop()

    def download_audio():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    return None, None
                base = ydl.prepare_filename(info)
                mp3_file = os.path.splitext(base)[0] + ".mp3"
                if not os.path.exists(mp3_file) and os.path.exists(base):
                    os.rename(base, mp3_file)
                if not os.path.exists(mp3_file):
                    return None, None
                return info, mp3_file
        except Exception as e:
            print(f"Download Error: {e}")
            return None, None

    info, file_path = await loop.run_in_executor(None, download_audio)

    if not info or not file_path or not os.path.exists(file_path):
        await status_msg.edit_text(
            "❌ Failed: Audio file could not be created.\n"
            "➡️ Most common causes: FFmpeg missing, region/cookie restriction, or yt-dlp extractor failure."
        )
        await asyncio.sleep(8)
        await status_msg.delete()
        return

    # Extract video info
    title = info.get("title", "Unknown Title")
    uploader = info.get("uploader", "Unknown Channel")
    views = info.get("view_count", 0)
    likes = info.get("like_count", 0)
    dislikes = info.get("dislike_count", "N/A")
    comments = info.get("comment_count", 0)
    categories = ", ".join(info.get("categories", [])) if info.get("categories") else "Unknown"
    url = info.get("webpage_url", "N/A")
    duration = str(datetime.utcfromtimestamp(info.get("duration", 0)).strftime("%H:%M:%S"))
    upload_date = info.get("upload_date")
    if upload_date:
        upload_date = datetime.strptime(upload_date, "%Y%m%d").strftime("%Y/%m/%d")
    else:
        upload_date = "Unknown"

    caption = (
        f"🎵 <b>{title}</b>\n"
        f"👤 Channel: {uploader}\n"
        f"📅 Uploaded: {upload_date}\n"
        f"⏱️ Length: {duration}\n"
        f"👁️ Views: {views:,}\n"
        f"👍 Likes: {likes:,}\n"
        f"👎 Dislikes: {dislikes}\n"
        f"💬 Comments: {comments:,}\n"
        f"📂 Category: {categories}\n"
        f"🔗 <a href='{url}'>Watch on YouTube</a>\n\n"
        f"🙋 Requested by: {update.effective_user.mention_html()}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/deweni2")]
    ])

    await status_msg.delete()
    await update.message.reply_audio(
        audio=open(file_path, "rb"),
        caption=caption,
        parse_mode="HTML",
        reply_markup=keyboard
    )

    os.remove(file_path)

import os
import yt_dlp
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import shutil
from datetime import datetime

MAIN_LOOP = None

def set_main_loop(loop):
    global MAIN_LOOP
    MAIN_LOOP = loop

def format_number(value):
    try:
        return f"{int(value):,}"
    except:
        return "N/A"

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        msg = await update.message.reply_text("Usage: /song <YouTube URL or keywords>")
        await asyncio.sleep(30)
        await msg.delete()
        return

    query = " ".join(context.args)

    # URL check / fallback to search
    if query.startswith("http://") or query.startswith("https://"):
        url = query
    else:
        url = f"ytsearch1:{query}"

    msg = await update.message.reply_text("🎵 Downloading audio, please wait...")

    os.makedirs("downloads", exist_ok=True)

    # FFmpeg check
    if not shutil.which("ffmpeg"):
        await msg.edit_text(
            "❌ FFmpeg is not installed or not in PATH.\n"
            "➡️ Please install FFmpeg from https://ffmpeg.org/download.html"
        )
        await asyncio.sleep(30)
        await msg.delete()
        return

    # cookies.txt check
    cookie_path = "modules/cookies.txt"
    if not os.path.exists(cookie_path):
        cookie_path = None  # optional fallback

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'nocheckcertificate': True,
        'noplaylist': True,
        'geo_bypass': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'tv', 'web_creator']
            }
        }
    }

    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

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
        await msg.edit_text(
            "❌ Failed: Audio file could not be created.\n"
            "➡️ Make sure FFmpeg is installed and cookies.txt exists if needed."
        )
        await asyncio.sleep(30)
        await msg.delete()
        return

    # Extract info
    title = info.get("title", "Unknown Title")
    uploader = info.get("uploader", "Unknown Channel")
    channel_url = info.get("channel_url", "")
    video_id = info.get("id", "")
    video_url = f"https://youtu.be/{video_id}" if video_id else "N/A"
    views = format_number(info.get("view_count"))
    likes = format_number(info.get("like_count"))
    dislikes = format_number(info.get("dislike_count"))
    comments = format_number(info.get("comment_count"))
    category = info.get("categories", ["N/A"])[0]

    # Upload date
    upload_date = info.get("upload_date")
    if upload_date:
        date_obj = datetime.strptime(upload_date, "%Y%m%d")
        date_str = date_obj.strftime("%Y/%m/%d")
        time_str = date_obj.strftime("%H:%M:%S")
    else:
        date_str = "N/A"
        time_str = "N/A"

    # Video length
    duration = info.get("duration")
    if duration:
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        length_str = f"{hours:02}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"
    else:
        length_str = "N/A"

    caption = (
        f"🎵 <b>{title}</b>\n"
        f"👤 Channel: <a href='{channel_url}'>{uploader}</a>\n"
        f"📺 Video: <a href='{video_url}'>Watch on YouTube</a>\n"
        f"📂 Category: {category}\n"
        f"📅 Uploaded: {date_str}\n"
        f"⏰ Time: {time_str} UTC\n"
        f"⏳ Length: {length_str}\n"
        f"👁️ Views: {views}\n"
        f"👍 Likes: {likes}\n"
        f"👎 Dislikes: {dislikes}\n"
        f"💬 Comments: {comments}\n\n"
        f"🙋 Requested by: {update.effective_user.mention_html()}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/deweni2")]
    ])

    await msg.delete()
    sent = await update.message.reply_audio(
        audio=open(file_path, "rb"),
        caption=caption,
        parse_mode="HTML",
        reply_markup=keyboard
    )

    os.remove(file_path)

    # auto delete after 30s
    await asyncio.sleep(30)
    await sent.delete()
    await update.message.delete()

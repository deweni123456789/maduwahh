import os
import yt_dlp
import asyncio
from datetime import datetime, timezone
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
        await asyncio.sleep(10)
        await msg.delete()
        return

    query = " ".join(context.args)

    # URL or search
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
        await asyncio.sleep(10)
        await status_msg.delete()
        return

    # cookies.txt check
    cookie_path = "modules/cookies.txt"
    if not os.path.exists(cookie_path):
        cookie_path = None

    # yt-dlp options
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }
        ],
        'postprocessor_args': ['-ar', '44100'],
        'prefer_ffmpeg': True,
        'quiet': True,
        'nocheckcertificate': True,
        'noplaylist': True,
        'geo_bypass': True,
        'extractor_args': {
            'youtube': {'player_client': ['ios', 'android', 'tv', 'web_creator']}
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
                if not os.path.exists(mp3_file):
                    for f in os.listdir("downloads"):
                        if f.lower().endswith(".mp3"):
                            mp3_file = os.path.join("downloads", f)
                            break
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
            "➡️ Make sure FFmpeg is installed and cookies.txt exists if needed."
        )
        await asyncio.sleep(10)
        await status_msg.delete()
        return

    # Extract metadata
    title = info.get("title", "Unknown Title")
    uploader = info.get("uploader", "Unknown Channel")
    views = info.get("view_count", 0)
    likes = info.get("like_count", "N/A")
    dislikes = info.get("dislike_count", "N/A")
    comments = info.get("comment_count", "N/A")
    duration = info.get("duration", 0)  # seconds
    upload_date = info.get("upload_date")  # format YYYYMMDD
    video_id = info.get("id")
    video_url = f"https://youtu.be/{video_id}" if video_id else "N/A"
    category = info.get("categories", ["N/A"])[0]

    # Format duration mm:ss
    if duration:
        mins, secs = divmod(duration, 60)
        hours, mins = divmod(mins, 60)
        length_str = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours else f"{mins:02d}:{secs:02d}"
    else:
        length_str = "N/A"

    # Format upload date
    if upload_date:
        try:
            dt = datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)
            date_str = dt.strftime("%Y/%m/%d")
            time_str = dt.strftime("%H:%M:%S")
        except Exception:
            date_str, time_str = "N/A", "N/A"
    else:
        date_str, time_str = "N/A", "N/A"

    caption = (
        f"🎵 <b>{title}</b>\n"
        f"👤 Channel: {uploader}\n"
        f"📺 <a href='{video_url}'>Watch on YouTube</a>\n"
        f"📂 Category: {category}\n"
        f"📅 Uploaded: {date_str}\n"
        f"⏰ Time: {time_str} UTC\n"
        f"⏳ Length: {length_str}\n"
        f"👁️ Views: {views:,}\n"
        f"👍 Likes: {likes}\n"
        f"👎 Dislikes: {dislikes}\n"
        f"💬 Comments: {comments}\n\n"
        f"🙋 Requested by: {update.effective_user.mention_html()}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/deweni2")]
    ])

    try:
        await update.message.reply_audio(
            audio=open(file_path, "rb"),
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as e:
        await status_msg.edit_text(f"⚠️ Upload failed: {e}")
        await asyncio.sleep(10)
        await status_msg.delete()
        return
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    # delete service "downloading..." message
    await status_msg.delete()

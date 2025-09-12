import os
import io
import uuid
import shutil
import subprocess
import asyncio
from datetime import datetime, timezone
from typing import Optional

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# -----------------------
# Helpers
# -----------------------
def format_number(v) -> str:
    try:
        return f"{int(v):,}"
    except Exception:
        return "N/A"

class YTDLLogger:
    def __init__(self):
        self.buf = io.StringIO()
    def debug(self, msg): self.buf.write(f"DEBUG: {msg}\n")
    def info(self, msg): self.buf.write(f"INFO: {msg}\n")
    def warning(self, msg): self.buf.write(f"WARN: {msg}\n")
    def error(self, msg): self.buf.write(f"ERROR: {msg}\n")
    def tail(self, n=3000):
        s = self.buf.getvalue()
        return s[-n:] if len(s) > n else s

# -----------------------
# Main handler (exported name)
# -----------------------
async def song_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /song <query or url>"""
    if not context.args:
        await update.message.reply_text("Usage: /song <YouTube URL or keywords>")
        return

    query = " ".join(context.args)
    is_url = query.startswith(("http://", "https://"))
    request_url = query if is_url else f"ytsearch1:{query}"

    status_msg = await update.message.reply_text("🎵 Preparing download...")

    os.makedirs("downloads", exist_ok=True)

    # ffmpeg check
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        await status_msg.edit_text(
            "❌ FFmpeg not found. Install ffmpeg and make sure it's in PATH (ffmpeg -version)."
        )
        await asyncio.sleep(6)
        try: await status_msg.delete()
        except: pass
        return

    # cookies: look for modules/cookies.txt or cookies.txt
    cookie_path: Optional[str] = None
    if os.path.exists("modules/cookies.txt"):
        cookie_path = "modules/cookies.txt"
    elif os.path.exists("cookies.txt"):
        cookie_path = "cookies.txt"

    # prepare logger
    ylog = YTDLLogger()

    # yt-dlp options
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": os.path.join("downloads", "%(title)s-%(id)s.%(ext)s"),
        "noplaylist": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "quiet": True,
        "prefer_ffmpeg": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "postprocessor_args": ["-ar", "44100"],
        "extractor_args": {"youtube": {"player_client": ["web"]}},
        "logger": ylog,
    }
    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path
    if ffmpeg_path:
        ydl_opts["ffmpeg_location"] = ffmpeg_path

    loop = asyncio.get_event_loop()

    def download_and_ensure_mp3():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(request_url, download=True)
                if not info:
                    return None, None, ylog.tail()

                if isinstance(info, dict) and info.get("entries"):
                    entries = info.get("entries")
                    if entries:
                        info = entries[0]

                base = ydl.prepare_filename(info)
                mp3_path = os.path.splitext(base)[0] + ".mp3"

                if os.path.exists(mp3_path):
                    return info, mp3_path, ylog.tail()

                possible_exts = [
                    os.path.splitext(base)[1], ".m4a", ".webm", ".opus", ".mp4",
                    ".mkv", ".flv", ".aac", ".wav", ".oga"
                ]
                possible_files = [os.path.splitext(base)[0] + ext for ext in possible_exts]
                found_source = next((p for p in possible_files if os.path.exists(p)), None)

                if not found_source:
                    return info, None, ylog.tail()

                try:
                    mp3_target = mp3_path
                    cmd = [ffmpeg_path, "-y", "-i", found_source, "-vn",
                           "-ab", "192k", "-ar", "44100", mp3_target]
                    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if proc.returncode != 0:
                        ylog.error(f"ffmpeg failed: rc={proc.returncode} stderr={proc.stderr}")
                        return info, None, ylog.tail() + "\nFFMPEG STDERR:\n" + proc.stderr
                    try: os.remove(found_source)
                    except: pass
                    if os.path.exists(mp3_target):
                        return info, mp3_target, ylog.tail()
                    return info, None, ylog.tail()
                except Exception as e:
                    ylog.error(f"ffmpeg convert exception: {e}")
                    return info, None, ylog.tail() + f"\nException: {e}"

        except Exception as e:
            ylog.error(f"yt-dlp exception: {e}")
            return None, None, ylog.tail() + f"\nException: {e}"

    info, mp3_file, logs = await loop.run_in_executor(None, download_and_ensure_mp3)

    if not info or not mp3_file or not os.path.exists(mp3_file):
        tail = logs or "No logs captured."
        msg_text = (
            "❌ Failed: Audio file could not be created.\n"
            "➡️ Most common causes: FFmpeg missing, region/cookie restriction, or yt-dlp extractor failure.\n\n"
            "— Debug logs (tail) —\n"
            f"{tail}\n\n"
            "Tips:\n"
            "• Update yt-dlp: `pip install -U yt-dlp`\n"
            "• If the video is restricted, export fresh cookies to modules/cookies.txt\n"
            "• For region-locked, enable proxy in ydl_opts['proxy']\n"
        )
        if len(msg_text) > 4000:
            msg_text = msg_text[-4000:]
        try:
            await status_msg.edit_text(msg_text)
        except:
            await update.message.reply_text(msg_text)
        return

    # --- success ---
    try:
        title = info.get("title", "Unknown Title")
        uploader = info.get("uploader", "Unknown Channel")
        channel_url = info.get("channel_url") or ""
        video_id = info.get("id") or ""
        video_url = info.get("webpage_url") or (f"https://youtu.be/{video_id}" if video_id else "N/A")
        views = format_number(info.get("view_count"))
        likes = format_number(info.get("like_count"))
        dislikes = format_number(info.get("dislike_count"))
        comments = format_number(info.get("comment_count"))
        categories = ", ".join(info.get("categories") or []) or "N/A"

        upload_date_field = info.get("upload_date")
        ts = info.get("release_timestamp") or info.get("timestamp")
        if ts:
            dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            date_str = dt.strftime("%Y/%m/%d")
            time_str = dt.strftime("%H:%M:%S")
        elif upload_date_field:
            try:
                dt = datetime.strptime(upload_date_field, "%Y%m%d")
                date_str = dt.strftime("%Y/%m/%d")
                time_str = "00:00:00"
            except:
                date_str, time_str = upload_date_field, "N/A"
        else:
            date_str, time_str = "N/A", "N/A"

        duration_sec = info.get("duration")
        if duration_sec:
            hrs, rem = divmod(duration_sec, 3600)
            mins, secs = divmod(rem, 60)
            duration_str = f"{int(hrs):02}:{int(mins):02}:{int(secs):02}" if hrs else f"{int(mins):02}:{int(secs):02}"
        else:
            duration_str = "N/A"

        try:
            size_mb = os.path.getsize(mp3_file) / (1024 * 1024)
            size_str = f"{size_mb:.2f} MB"
        except:
            size_str = "N/A"

        bot_name = (context.bot.first_name or context.bot.username or "Bot")

        caption = (
            f"🎵 <b>{title}</b>\n"
            f"👤 Channel: <a href='{channel_url}'>{uploader}</a>\n"
            f"📺 <a href='{video_url}'>Watch on YouTube</a>\n"
            f"📂 Category: {categories}\n"
            f"📅 Uploaded: {date_str}\n"
            f"⏰ Time: {time_str} UTC\n"
            f"⏳ Length: {duration_str}\n"
            f"👁️ Views: {views}\n"
            f"👍 Likes: {likes}\n"
            f"👎 Dislikes: {dislikes}\n"
            f"📦 File size: {size_str}\n"
            f"💬 Comments: {comments}\n\n"
            f"🙋 Requested by: {update.effective_user.mention_html()}\n"
            f"🤖 Uploaded by: {bot_name}"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/deweni2"),
                InlineKeyboardButton("📢 Support Group", url="https://t.me/slmusicmania")
            ],
            [
                InlineKeyboardButton("💌 Contact Bot", url=f"https://t.me/{context.bot.username}"),
                InlineKeyboardButton("🌺 Open in YouTube 🌺", url=video_url)
            ]
        ])

        try: await status_msg.delete()
        except: pass

        with open(mp3_file, "rb") as f:
            await update.message.reply_audio(
                audio=f,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
                title=title,
                performer=uploader
            )

    finally:
        try:
            if mp3_file and os.path.exists(mp3_file):
                os.remove(mp3_file)
        except:
            pass

    return

# song.py (robust fix with ffmpeg fallback + debug logs)
import os
import yt_dlp
import asyncio
import shutil
import subprocess
import io
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

MAIN_LOOP = None
def set_main_loop(loop):
    global MAIN_LOOP
    MAIN_LOOP = loop

def format_number(value):
    try:
        return f"{int(value):,}"
    except:
        return "N/A"

class YTDLLogger:
    def __init__(self, buf):
        self.buf = buf
    def debug(self, msg):
        try: self.buf.write(f"DEBUG: {msg}\n")
        except: pass
    def info(self, msg):
        try: self.buf.write(f"INFO: {msg}\n")
        except: pass
    def warning(self, msg):
        try: self.buf.write(f"WARN: {msg}\n")
        except: pass
    def error(self, msg):
        try: self.buf.write(f"ERROR: {msg}\n")
        except: pass

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # usage check
    if not context.args:
        msg = await update.message.reply_text("Usage: /song <YouTube URL or keywords>")
        await asyncio.sleep(20)
        try: await msg.delete()
        except: pass
        return

    query = " ".join(context.args)
    # allow url or fallback to search
    if query.startswith("http://") or query.startswith("https://"):
        url = query
    else:
        url = f"ytsearch1:{query}"

    status_msg = await update.message.reply_text("🎵 Downloading audio — preparing...")

    # ensure downloads dir
    os.makedirs("downloads", exist_ok=True)

    # ffmpeg check
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        await status_msg.edit_text(
            "❌ FFmpeg not found in PATH.\n"
            "➡️ Please install FFmpeg and make sure it's accessible (ffmpeg -version)."
        )
        await asyncio.sleep(20)
        try: await status_msg.delete()
        except: pass
        return

    # cookies optional
    cookie_path = "modules/cookies.txt"
    if not os.path.exists(cookie_path):
        cookie_path = None

    # prepare logger buffer for debugging
    log_buf = io.StringIO()
    ytdl_logger = YTDLLogger(log_buf)

    # yt-dlp options (prefer m4a first for better postprocessing reliability)
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": "downloads/%(title)s-%(id)s.%(ext)s",
        "noplaylist": True,
        "nocheckcertificate": True,
        "prefer_ffmpeg": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "postprocessor_args": ["-ar", "44100"],
        "ffmpeg_location": ffmpeg_path,
        "logger": ytdl_logger,
        "quiet": True,    # keep yt-dlp quiet; logs go to our buffer
        "no_warnings": True,
        "geo_bypass": True,
        "extractor_args": {"youtube": {"player_client": ["web", "android", "ios"]}}
    }
    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path

    loop = MAIN_LOOP or asyncio.get_event_loop()

    def download_and_ensure_mp3():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    ytdl_logger.error("yt-dlp returned no info object")
                    return None, None, log_buf.getvalue()

                # ytsearch returns entries
                if isinstance(info, dict) and "entries" in info:
                    entries = info.get("entries") or []
                    if entries:
                        info = entries[0]

                # prepare expected base filename
                base = ydl.prepare_filename(info)  # downloads/title-id.ext
                mp3_path = os.path.splitext(base)[0] + ".mp3"

                # if postprocessor created mp3, return it
                if os.path.exists(mp3_path):
                    ytdl_logger.info(f"MP3 already exists: {mp3_path}")
                    return info, mp3_path, log_buf.getvalue()

                # else check for original downloaded file (several possible exts)
                possible = []
                ext_from_info = info.get("ext")
                if ext_from_info:
                    possible.append(os.path.splitext(base)[0] + f".{ext_from_info}")
                for ext in [".m4a", ".webm", ".opus", ".mp4", ".mkv", ".flv", ".aac", ".wav", ".oga"]:
                    possible.append(os.path.splitext(base)[0] + ext)

                found = None
                for p in possible:
                    if os.path.exists(p):
                        found = p
                        break

                if not found:
                    ytdl_logger.error("No downloaded source file found to convert to mp3.")
                    return info, None, log_buf.getvalue()

                # convert with ffmpeg as fallback
                try:
                    cmd = [ffmpeg_path, "-y", "-i", found, "-vn", "-ab", "192k", "-ar", "44100", mp3_path]
                    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if proc.returncode != 0:
                        ytdl_logger.error(f"ffmpeg returned non-zero ({proc.returncode}): {proc.stderr}")
                        return info, None, log_buf.getvalue() + "\nFFMPEG STDERR:\n" + proc.stderr
                    # remove original download if conversion ok
                    try:
                        os.remove(found)
                    except Exception:
                        pass
                    if os.path.exists(mp3_path):
                        ytdl_logger.info(f"Successfully converted to mp3: {mp3_path}")
                        return info, mp3_path, log_buf.getvalue()
                    else:
                        ytdl_logger.error("ffmpeg conversion claims success but mp3 missing")
                        return info, None, log_buf.getvalue()
                except Exception as e:
                    ytdl_logger.error(f"Exception running ffmpeg: {e}")
                    return info, None, log_buf.getvalue() + f"\nException: {e}"

        except Exception as e:
            ytdl_logger.error(f"yt-dlp raised exception: {e}")
            return None, None, log_buf.getvalue() + f"\nException: {e}"

    # run download/convert in executor to avoid blocking
    info, mp3_file, debug_logs = await loop.run_in_executor(None, download_and_ensure_mp3)

    if not info or not mp3_file or not os.path.exists(mp3_file):
        # send helpful debug message to user (trim logs if too long)
        tail = debug_logs[-3500:] if debug_logs else "No logs captured."
        await status_msg.edit_text(
            "❌ Failed: Audio file could not be created.\n"
            "➡️ Most common causes: FFmpeg missing, region/cookie restriction, or yt-dlp extractor failure.\n\n"
            "— Debug logs (tail) —\n"
            f"{tail}\n\n"
            "Try: `ffmpeg -version` and `yt-dlp --version` inside your environment, and ensure cookies.txt exists for restricted videos."
        )
        return

    # Prepare metadata for caption
    try:
        # if search returned an entry with limited fields, info could be nested earlier. ensure dict
        title = info.get("title", "Unknown Title")
        uploader = info.get("uploader", "Unknown Channel")
        channel_url = info.get("channel_url", "")
        video_id = info.get("id", "")
        video_url = f"https://youtu.be/{video_id}" if video_id else "N/A"
        views = format_number(info.get("view_count"))
        likes = format_number(info.get("like_count"))
        dislikes = format_number(info.get("dislike_count"))
        comments = format_number(info.get("comment_count"))
        category = (info.get("categories") or ["N/A"])[0]

        upload_date = info.get("upload_date")  # YYYYMMDD
        if upload_date:
            try:
                dt = datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)
                date_str = dt.strftime("%Y/%m/%d")
                time_str = dt.strftime("%H:%M:%S")
            except Exception:
                date_str = upload_date
                time_str = "N/A"
        else:
            date_str, time_str = "N/A", "N/A"

        duration = info.get("duration")
        if duration:
            mins, secs = divmod(duration, 60)
            hours, mins = divmod(mins, 60)
            length_str = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours else f"{mins:02d}:{secs:02d}"
        else:
            length_str = "N/A"

        # file size
        try:
            file_size_mb = os.path.getsize(mp3_file) / (1024*1024)
            size_str = f"{file_size_mb:.2f} MB"
        except:
            size_str = "N/A"

    except Exception as e:
        # fallback minimal caption
        await status_msg.edit_text(f"⚠️ Downloaded but failed to read metadata: {e}")
        # continue with minimal info
        title = info.get("title", "Unknown Title") if info else "Unknown Title"
        uploader = info.get("uploader", "Unknown Channel") if info else "Unknown Channel"
        channel_url = info.get("channel_url", "") if info else ""
        video_url = f"https://youtu.be/{info.get('id')}" if info and info.get('id') else "N/A"
        category = (info.get("categories") or ["N/A"])[0] if info else "N/A"
        date_str = time_str = length_str = views = likes = dislikes = comments = size_str = "N/A"

    caption = (
        f"🎵 <b>{title}</b>\n"
        f"👤 Channel: <a href='{channel_url}'>{uploader}</a>\n"
        f"📺 <a href='{video_url}'>Watch on YouTube</a>\n"
        f"📂 Category: {category}\n"
        f"📅 Uploaded: {date_str}\n"
        f"⏰ Time: {time_str} UTC\n"
        f"⏳ Length: {length_str}\n"
        f"👁️ Views: {views}\n"
        f"👍 Likes: {likes}\n"
        f"👎 Dislikes: {dislikes}\n"
        f"💬 Comments: {comments}\n"
        f"💾 Size: {size_str}\n\n"
        f"🙋 Requested by: {update.effective_user.mention_html()}"
    )

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/deweni2")]])

    # delete the status message before sending final file (keeps chat clean)
    try:
        await status_msg.delete()
    except:
        pass

    # send audio
    try:
        with open(mp3_file, "rb") as f:
            sent = await update.message.reply_audio(
                audio=f,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )
    except Exception as e:
        # if upload failed, send debug logs too
        tail = debug_logs[-3500:] if debug_logs else "No logs."
        await update.message.reply_text(f"⚠️ Upload failed: {e}\n\n— logs —\n{tail}")
        # cleanup file
        try: os.remove(mp3_file)
        except: pass
        return

    # cleanup local mp3
    try:
        os.remove(mp3_file)
    except:
        pass

    # optionally delete the user's command to keep chat clean (comment out if not wanted)
    try:
        await update.message.delete()
    except:
        pass

    return

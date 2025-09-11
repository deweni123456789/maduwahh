import os
import re
import yt_dlp
import shutil
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from datetime import datetime

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        return await update.message.reply_text(
            "⚠️ Please provide a video name.\n\nExample: /video despacito"
        )

    # Send initial status message
    status = await update.message.reply_text("🔎 Searching for video…")
    os.makedirs("downloads", exist_ok=True)
    out_tmpl = os.path.join("downloads", "%(title)s [%(id)s].%(ext)s")

    # Check FFmpeg
    if not shutil.which("ffmpeg"):
        return await status.edit_text("❌ FFmpeg is not installed. Please install it!")

    cookie_file = "cookies.txt" if os.path.exists("cookies.txt") else None

    ydl_opts = {
        "format": "bv*+ba/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "outtmpl": out_tmpl,
        "quiet": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "default_search": "ytsearch",
        "extractor_args": {"youtube": {"player_client": ["web"]}},  # only web client
    }

    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(query, download=True)
            except Exception:
                info = ydl.extract_info(f"ytsearch1:{query}", download=True)

            if "entries" in info:
                info = info["entries"][0]

            file_path = ydl.prepare_filename(info)

            # fix webm → mp4
            if not file_path.endswith(".mp4") and os.path.exists(file_path.replace(".webm", ".mp4")):
                file_path = file_path.replace(".webm", ".mp4")

            if not os.path.exists(file_path):
                return await status.edit_text("❌ File not found after download.")
    except Exception as e:
        return await status.edit_text(f"❌ Failed: `{e}`")

    # --- Metadata ---
    upload_date_raw = info.get('upload_date')
    try:
        upload_date = datetime.strptime(str(upload_date_raw), "%Y%m%d").strftime("%Y/%m/%d")
    except:
        upload_date = upload_date_raw

    def safe_int(val):
        try:
            return int(val)
        except:
            return 0

    duration = safe_int(info.get('duration'))
    views = safe_int(info.get('view_count'))
    likes = safe_int(info.get('like_count'))
    comments = safe_int(info.get('comment_count'))

    caption = (
        f"🎥 **Title:** {info.get('title')}\n"
        f"📺 **Channel:** {info.get('uploader')}\n"
        f"📅 **Upload Date:** {upload_date}\n"
        f"⏱ **Duration:** {duration} sec\n"
        f"👁 **Views:** {views}\n"
        f"👍 **Likes:** {likes}\n"
        f"💬 **Comments:** {comments}\n\n"
        f"🙋‍♂️ **Requested by:** {update.message.from_user.mention}"
    )

    try:
        await update.message.reply_video(
            video=file_path,
            caption=caption,
            supports_streaming=True,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/deweni2")]]
            )
        )
    except Exception as e:
        await status.edit_text(f"⚠️ Error while sending video: `{e}`")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    await status.delete()

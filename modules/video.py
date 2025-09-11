import os
import re
import yt_dlp
import logging
from datetime import datetime
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Please provide a video name.\n\nExample: /video despacito"
        )
        return

    query = " ".join(context.args)
    status = await update.message.reply_text("🔎 Searching for video…")

    os.makedirs("downloads", exist_ok=True)
    out_tmpl = os.path.join("downloads", "%(title)s [%(id)s].%(ext)s")

    cookie_file = "cookies.txt" if os.path.exists("cookies.txt") else None

    ydl_opts = {
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "outtmpl": out_tmpl,
        "quiet": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "default_search": "ytsearch",
        "extractor_args": {"youtube": {"player_skip": ["configs", "webpage"]}},
    }
    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    info = None
    file_path = None

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # 🔹 First attempt: direct query
                info = ydl.extract_info(query, download=True)
            except Exception as e:
                if "not available on this app" in str(e).lower():
                    logging.warning("Retrying with ytsearch1 because of app restriction…")
                    info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                else:
                    raise

            if "entries" in info:
                info = info["entries"][0]

            file_path = ydl.prepare_filename(info)

            if not file_path.endswith(".mp4") and os.path.exists(file_path.replace(".webm", ".mp4")):
                file_path = file_path.replace(".webm", ".mp4")

            if not os.path.exists(file_path):
                await status.edit_text(f"❌ File not found: {file_path}")
                return

    except Exception as e:
        await status.edit_text(f"❌ Failed: `{e}`")
        return

    # --- Metadata formatting ---
    upload_date_raw = info.get("upload_date")
    try:
        upload_date = datetime.strptime(str(upload_date_raw), "%Y%m%d").strftime("%Y/%m/%d")
    except Exception:
        upload_date = upload_date_raw

    def safe_int(val):
        try:
            return int(val)
        except Exception:
            return 0

    duration = safe_int(info.get("duration"))
    views = safe_int(info.get("view_count"))
    likes = safe_int(info.get("like_count"))
    comments = safe_int(info.get("comment_count"))

    caption = (
        f"🎥 <b>Title:</b> {info.get('title')}\n"
        f"📺 <b>Channel:</b> {info.get('uploader')}\n"
        f"📅 <b>Upload Date:</b> {upload_date}\n"
        f"⏱ <b>Duration:</b> {duration} sec\n"
        f"👁 <b>Views:</b> {views}\n"
        f"👍 <b>Likes:</b> {likes}\n"
        f"💬 <b>Comments:</b> {comments}\n\n"
        f"🙋‍♂️ <b>Requested by:</b> {update.effective_user.mention_html()}"
    )

    try:
        await update.message.reply_video(
            video=file_path,
            caption=caption,
            parse_mode="HTML",
            supports_streaming=True,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(
                    "👨‍💻 Developer",
                    url=f"https://t.me/{config.DEVELOPER.replace('@','')}"
                )]]
            )
        )
    except Exception as e:
        logging.error(f"Send video error: {e}")
        await update.message.reply_text("⚠️ Error while sending video.")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

    await status.delete()

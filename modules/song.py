import os
import asyncio
import yt_dlp
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

# -----------------------
# /song Command Handler
# -----------------------
async def song_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🎵 Please provide a song name.\nExample: `/song sanam re`", parse_mode="Markdown")
        return

    query = " ".join(context.args)
    user = update.effective_user
    msg = await update.message.reply_text(f"🔎 Searching for: <b>{query}</b> ...", parse_mode="HTML")

    ydl_opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "cookiefile": "cookies.txt" if os.path.exists("cookies.txt") else None,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": "%(id)s.%(ext)s"
    }

    loop = asyncio.get_running_loop()

    try:
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(f"ytsearch1:{query}", download=True)

        info = await loop.run_in_executor(None, download)

        if "entries" in info:
            info = info["entries"][0]

        file_id = f"{info['id']}.mp3"
        title = info.get("title", "Unknown Title")
        channel = info.get("channel", "Unknown Channel")
        upload_date = info.get("upload_date", "")
        views = info.get("view_count", 0)
        likes = info.get("like_count", 0)
        dislikes = info.get("dislike_count", 0)
        comments = info.get("comment_count", 0)
        categories = ", ".join(info.get("categories", []))
        url = info.get("webpage_url", "N/A")
        duration = str(datetime.utcfromtimestamp(info["duration"]).strftime("%H:%M:%S")) if "duration" in info else "N/A"

        upload_dt = ""
        if upload_date:
            dt = datetime.strptime(upload_date, "%Y%m%d")
            upload_dt = dt.strftime("%Y/%m/%d")

        caption = (
            f"🎶 <b>{title}</b>\n"
            f"👤 Channel: <b>{channel}</b>\n"
            f"📅 Uploaded: <b>{upload_dt}</b>\n"
            f"⏱️ Length: <b>{duration}</b>\n"
            f"👀 Views: <b>{views:,}</b>\n"
            f"👍 Likes: <b>{likes:,}</b> | 👎 Dislikes: <b>{dislikes:,}</b>\n"
            f"💬 Comments: <b>{comments:,}</b>\n"
            f"📂 Category: <b>{categories}</b>\n"
            f"🔗 <a href='{url}'>Watch on YouTube</a>\n\n"
            f"📌 Requested by {user.mention_html()}"
        )

        await msg.delete()
        await update.message.reply_audio(
            audio=open(file_id, "rb"),
            title=title,
            performer=channel,
            caption=caption,
            parse_mode="HTML"
        )

        os.remove(file_id)

    except Exception as e:
        await msg.edit_text(f"❌ Failed: Audio file could not be created.\n\n<b>Error:</b> {e}", parse_mode="HTML")

import os
import re
import yt_dlp
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime


def register(app):
    def sanitize_filename(name):
        return re.sub(r'[\\/*?:"<>|]', "", name)

    @app.on_message(filters.command("video"))
    async def video_handler(client, message):
        query = " ".join(message.command[1:])
        if not query:
            return await message.reply_text(
                "⚠️ Please provide a video name.\n\nExample: `/video despacito`"
            )

        status = await message.reply_text("🔎 Searching for video…")
        os.makedirs("downloads", exist_ok=True)
        out_tmpl = os.path.join("downloads", "%(title)s [%(id)s].%(ext)s")

        cookie_file = "cookies.txt" if os.path.exists("cookies.txt") else None

        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "outtmpl": out_tmpl,
            "quiet": True,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "default_search": "ytsearch",
        }

        if cookie_file:
            ydl_opts["cookiefile"] = cookie_file

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=True)
                if "entries" in info:
                    info = info["entries"][0]

                # ✅ Get actual downloaded file path
                file_path = ydl.prepare_filename(info)

                # Sometimes yt-dlp saves as .webm first → then .mp4 after merge
                if not file_path.endswith(".mp4") and os.path.exists(file_path.replace(".webm", ".mp4")):
                    file_path = file_path.replace(".webm", ".mp4")

                if not os.path.exists(file_path):
                    return await status.edit(f"❌ File not found: {file_path}")

        except Exception as e:
            return await status.edit(f"❌ Failed: `{e}`")

        # --- Upload date YYYY/MM/DD ---
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
            f"🙋‍♂️ **Requested by:** {message.from_user.mention}"
        )

        try:
            await client.send_video(
                chat_id=message.chat.id,
                video=file_path,
                caption=caption,
                supports_streaming=True,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(
                        "👨‍💻 Developer",
                        url=f"https://t.me/{config.DEVELOPER.replace('@','')}"
                    )]]
                )
            )
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

        await status.delete()

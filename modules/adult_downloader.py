# modules/adult_downloader.py
import os
import time
import asyncio
import yt_dlp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.progress import progress_callback

DOWNLOAD_DIR = os.path.join("downloads", "adult")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = 1.9 * 1024 * 1024 * 1024  # ~1.9 GB (Telegram bot max limit for premium)

async def download_adult(update, context, url: str):
    message = update.effective_message

    # Allow only private chats
    if message.chat.type != "private":
        await message.reply_text("🚫 This command only works in private chat.")
        return

    if not url or not isinstance(url, str):
        await message.reply_text("❌ Please provide a valid video link.\nUsage: /adult <link>")
        return

    try:
        status_msg = await message.reply_text("🔞 Processing your request...")
    except Exception:
        status_msg = None

    loop = asyncio.get_running_loop()
    last_update = {"t": 0.0}
    finished = {"val": False}

    def hook(d):
        status = d.get("status")
        if status == "downloading" and not finished["val"] and status_msg:
            now = time.time()
            if now - last_update["t"] < 1.0:
                return
            last_update["t"] = now
            downloaded = d.get("downloaded_bytes", 0) or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            asyncio.run_coroutine_threadsafe(
                progress_callback(downloaded, total, status_msg, "⬇️ Downloading"),
                loop
            )
        elif status == "finished":
            finished["val"] = True

    # yt-dlp options — limit to 360p
    ydl_opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "format": "bestvideo[height<=360]+bestaudio/best[height<=360]",
        "noplaylist": True,
        "merge_output_format": "mp4",
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": True,
    }

    def run_download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if isinstance(info, dict) and "entries" in info:
                info = info["entries"][0]
            file_path = ydl.prepare_filename(info)
            return file_path, info

    try:
        filepath, info = await asyncio.to_thread(run_download)
    except Exception as e:
        if status_msg:
            await status_msg.edit_text(f"❌ Download failed: {e}")
        else:
            await message.reply_text(f"❌ Download failed: {e}")
        return

    # Delete status message
    try:
        if status_msg:
            await status_msg.delete()
    except Exception:
        pass

    # Compress if file too big
    if os.path.getsize(filepath) > MAX_FILE_SIZE:
        compressed_path = filepath.replace(".mp4", "_compressed.mp4")
        await message.reply_text("⚙️ File too large, compressing to fit Telegram limit...")
        os.system(
            f'ffmpeg -i "{filepath}" -vf scale=-2:360 -b:v 1000k -b:a 128k "{compressed_path}" -y'
        )
        os.remove(filepath)
        filepath = compressed_path

    # If still too big, send link instead
    if os.path.getsize(filepath) > MAX_FILE_SIZE:
        dl_link = info.get("url") or url
        await message.reply_text(
            f"⚠️ File is too large to send on Telegram.\n\n🔗 Direct Download: {dl_link}"
        )
        try:
            os.remove(filepath)
        except Exception:
            pass
        return

    # Prepare caption
    title = info.get("title") or "Unknown Title"
    uploader = info.get("uploader") or info.get("uploader_id") or "Unknown"
    views = info.get("view_count") or 0
    likes = info.get("like_count", "N/A")
    dislikes = info.get("dislike_count", "N/A")
    comments = info.get("comment_count", "N/A")

    caption = (
        f"📹 <b>{title}</b>\n"
        f"👤 Channel: {uploader}\n"
        f"👁 Views: {views:,}\n"
        f"👍 Likes: {likes}\n"
        f"👎 Dislikes: {dislikes}\n"
        f"💬 Comments: {comments}\n\n"
        f"Requested by: {message.from_user.first_name}"
    )

    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("💻 Contact Developer", url="https://t.me/deweni2")]]
    )

    # Try sending as video
    try:
        with open(filepath, "rb") as f:
            await message.reply_video(
                video=f,
                caption=caption,
                parse_mode="HTML",
                reply_markup=buttons,
                supports_streaming=True
            )
    except Exception:
        try:
            with open(filepath, "rb") as f:
                await message.reply_document(
                    document=f,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=buttons
                )
        except Exception as e_doc:
            await message.reply_text(f"❌ Upload failed: {e_doc}")

    # Cleanup
    try:
        os.remove(filepath)
    except Exception:
        pass

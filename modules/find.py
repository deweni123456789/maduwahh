import os
import tempfile
import logging
import aiohttp
import subprocess
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

AUDD_API_KEY = os.getenv("AUDD_API_KEY", "58aea691c04ed4a29ba2e7a6c2fcc478")

async def find_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = None

    if update.message.audio:
        file = await update.message.audio.get_file()
    elif update.message.voice:
        file = await update.message.voice.get_file()
    elif update.message.video_note:
        file = await update.message.video_note.get_file()
    elif update.message.video:
        file = await update.message.video.get_file()

    if not file:
        await update.message.reply_text("📂 Send me any voice, audio, or video under 30 seconds — I’ll find your song instantly.")
        return

    temp_dir = tempfile.gettempdir()
    raw_path = os.path.join(temp_dir, f"{file.file_unique_id}")
    mp3_path = os.path.join(temp_dir, f"{file.file_unique_id}.mp3")

    await file.download_to_drive(raw_path)

    # Convert to mp3 if not already
    if not raw_path.lower().endswith(".mp3"):
        try:
            subprocess.run(["ffmpeg", "-y", "-i", raw_path, mp3_path], check=True)
            os.remove(raw_path)
        except Exception as e:
            await update.message.reply_text(f"⚠️ Audio convert error: {e}")
            return
    else:
        mp3_path = raw_path

    try:
        async with aiohttp.ClientSession() as session:
            with open(mp3_path, "rb") as f:
                form = aiohttp.FormData()
                form.add_field("api_token", AUDD_API_KEY)
                form.add_field("file", f, filename="audio.mp3")
                form.add_field("return", "apple_music,spotify,youtube")

                async with session.post("https://api.audd.io/", data=form) as resp:
                    result = await resp.json()

        logging.info(f"AUDD Response: {result}")

        if not result.get("result"):
            err_msg = result.get("error", {}).get("error_message", "ගීතය හඳුනාගන්න බැරි වුණා.")
            await update.message.reply_text(f"❌ {err_msg}")
            return

        music_data = result["result"]
        title = music_data.get("title", "Unknown Title")
        artist = music_data.get("artist", "Unknown Artist")
        album = music_data.get("album", "Unknown Album")
        release_date = music_data.get("release_date", "N/A")
        label = music_data.get("label", "N/A")
        genre = ", ".join(music_data.get("genre", [])) if isinstance(music_data.get("genre"), list) else music_data.get("genre", "N/A")
        duration = music_data.get("timecode", "N/A")
        song_link = music_data.get("song_link", "")
        spotify_url = music_data.get("spotify", {}).get("external_urls", {}).get("spotify")
        cover_url = music_data.get("spotify", {}).get("album", {}).get("images", [{}])[0].get("url")

        youtube_link = ""
        if music_data.get("youtube"):
            youtube_link = f"https://www.youtube.com/watch?v={music_data['youtube']['video_id']}"

        caption = (
            f"🎵 <b>{title}</b>\n"
            f"👤 <i>{artist}</i>\n"
            f"💿 {album}\n"
            f"📅 {release_date}\n"
            f"🏷 {label}\n"
            f"🎼 {genre}\n"
            f"⏱ {duration}"
        )

        # Buttons
        buttons = []
        if song_link:
            buttons.append([InlineKeyboardButton("▶️ Listen", url=song_link)])
        if spotify_url:
            buttons.append([InlineKeyboardButton("🎧 Spotify", url=spotify_url)])
        if youtube_link:
            buttons.append([InlineKeyboardButton("⬇ Download from YouTube", url=youtube_link)])
        buttons.append([InlineKeyboardButton("💬 Developer Contact", url="https://t.me/deweni2")])

        keyboard = InlineKeyboardMarkup(buttons)

        if cover_url:
            await update.message.reply_photo(
                photo=cover_url,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )

    except Exception as e:
        logging.error(f"Find music error: {e}")
        await update.message.reply_text("⚠️ Song finding error ")
    finally:
        try:
            os.remove(mp3_path)
        except:
            pass

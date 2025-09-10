import os
import re
import yt_dlp
import asyncio
import time
from pyrogram.errors import FloodWait
from utils.progress import progress_callback

MAIN_LOOP = None  # Store main loop for async updates

def set_main_loop(loop):
    global MAIN_LOOP
    MAIN_LOOP = loop

def safe_filename(path):
    """Sanitize filename for Windows."""
    dirname = os.path.dirname(path)
    basename = os.path.basename(path)
    safe = re.sub(r'[\\/*?:"<>|]', "_", basename)
    return os.path.join(dirname, safe)

def _download_media(query, progress_msg=None, search_mode=True, is_audio=True):
    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    def hook(d):
        """yt-dlp progress hook."""
        if d.get('status') == 'downloading' and progress_msg and MAIN_LOOP:
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 1
            asyncio.run_coroutine_threadsafe(
                progress_callback(downloaded, total, progress_msg, prefix="⬇️ Downloading"),
                MAIN_LOOP
            )

    outtmpl = os.path.join(DOWNLOAD_DIR, "%(title).200s.%(ext)s")

    # 🔧 Common yt-dlp options
    common_opts = {
        "noplaylist": True,
        "progress_hooks": [hook] if hook else [],
        "outtmpl": outtmpl,
        "ignoreerrors": True,
        "retries": 5,
        "quiet": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            )
        },
    }

    if is_audio:
        # ✅ Audio fallback chain: m4a → webm → mp4 → bestaudio
        ydl_opts = {
            **common_opts,
            "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio[ext=mp4]/bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
    else:
        # ✅ Video fallback chain: mp4 → webm → best
        ydl_opts = {
            **common_opts,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
        }

    # ✅ Cookies support for Instagram / YouTube
    cookies_path = os.path.join(os.path.dirname(__file__), "cookies.txt")
    if os.path.exists(cookies_path):
        ydl_opts["cookiefile"] = cookies_path

    target = f"ytsearch1:{query}" if search_mode else query

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target, download=True)
            if isinstance(info, dict) and 'entries' in info:
                info = info['entries'][0]

            filename = safe_filename(ydl.prepare_filename(info))

            # fallback if file not found
            if not os.path.exists(filename):
                files = [
                    os.path.join(DOWNLOAD_DIR, f)
                    for f in os.listdir(DOWNLOAD_DIR)
                    if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))
                ]
                if files:
                    filename = max(files, key=os.path.getmtime)

            return filename, info

    except FloodWait as e:
        print(f"FloodWait: sleeping for {e.value} seconds")
        time.sleep(e.value)
        return _download_media(query, progress_msg, search_mode, is_audio)

# ✅ Public functions
def download_audio(query, progress_msg=None, search_mode=True):
    return _download_media(query, progress_msg, search_mode, is_audio=True)

def download_video(query, progress_msg=None, search_mode=True):
    return _download_media(query, progress_msg, search_mode, is_audio=False)

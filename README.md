# Telegram Downloader Bot

This package contains a Telegram bot that can download audio and video using `yt-dlp`.

## Commands
- `/song <query or URL>` — download audio (mp3). If you pass a plain query, the bot will search YouTube.
- `/video <query or URL>` — download video (mp4).
- `/fb <url>` — download Facebook video.
- `/tiktok <url>` — download TikTok video.
- `/insta <url>` — download Instagram media.

## Requirements
- Python 3.10+
- `ffmpeg` installed on the system (required by yt-dlp for conversions).
- Install Python requirements:
```bash
pip install -r requirements.txt
```

## Setup
1. Create a bot with BotFather and obtain the token.
2. Set env var:
```bash
export TELEGRAM_BOT_TOKEN="123:ABC..."
```
or edit `main.py` to paste your token (not recommended for security).
3. Run:
```bash
python main.py
```

## Notes & Limitations
- This code uses `yt-dlp` which supports many sites including YouTube, Facebook, TikTok, Instagram. Site support and behavior can change over time.
- Large downloads may exceed Telegram's file size limits (max file size depends on bot account limits). You may need to host files externally.
- The author provides this as a starting point. You should test locally and adapt (timeouts, rate limits, storage cleanup).

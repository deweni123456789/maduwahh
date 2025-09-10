import requests
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from bs4 import BeautifulSoup

BOT_TOKEN = "8400227620:AAEeHTBl9_s4Z0Sh4546UNKH8ozVEZEzyK4"  # Optional: move to config
GENIUS_TOKEN = "na1gw1IAVjVFHRcLJ7zXNlqCyEa1u-h4rZQUE7uSZJf78RJGdsyHn28ZhM2Hwthm"

# ==== COMMAND: LYRICS ====
async def lyrics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Please provide a song name.\nExample: `/lyrics Shape of You`")
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"🔍 Searching lyrics for: {query}")

    headers = {"Authorization": f"Bearer {GENIUS_TOKEN}"}
    search_url = "https://api.genius.com/search"
    search_res = requests.get(search_url, headers=headers, params={"q": query})

    if search_res.status_code != 200:
        await update.message.reply_text("❌ Genius API error.")
        return

    data = search_res.json()
    hits = data["response"]["hits"]
    if not hits:
        await update.message.reply_text("❌ No lyrics found.")
        return

    song_url = hits[0]["result"]["url"]
    page = requests.get(song_url).text

    soup = BeautifulSoup(page, "html.parser")
    lyrics_divs = soup.find_all("div", {"data-lyrics-container": "true"})
    lyrics = "\n".join([div.get_text(separator="\n") for div in lyrics_divs])

    if not lyrics:
        await update.message.reply_text("❌ Couldn't extract lyrics.")
        return

    if len(lyrics) > 4000:
        lyrics = lyrics[:3990] + "\n... (truncated)"
    await update.message.reply_text(f"🎶 Lyrics for *{query}*:\n\n{lyrics}", parse_mode="Markdown")


def add_lyrics_handler(application):
    """Attach lyrics command to the bot."""
    application.add_handler(CommandHandler("lyrics", lyrics_command))

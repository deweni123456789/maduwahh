# modules/broadcast.py
import os
import json
from typing import Dict
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

# Config
CHAT_FILE = os.getenv("CHAT_FILE", "chats.json")
BOT_OWNER_USERNAME = os.getenv("BOT_OWNER", "deweni2")  # without @

# Load & save
def _load_chats() -> Dict[str, list]:
    try:
        with open(CHAT_FILE, "r") as f:
            data = json.load(f)
            return {
                "users": data.get("users", []),
                "groups": data.get("groups", []),
                "channels": data.get("channels", []),
            }
    except:
        return {"users": [], "groups": [], "channels": []}

def _save_chats(data: Dict[str, list]) -> None:
    tmp = CHAT_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, CHAT_FILE)

# Track chats
async def track_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        if user and getattr(user, "is_bot", False):
            return

        chat = update.effective_chat
        if not chat:
            return

        data = _load_chats()
        cid = chat.id
        ctype = chat.type

        if ctype == "private" and cid not in data["users"]:
            data["users"].append(cid)
        elif ctype in ("group", "supergroup") and cid not in data["groups"]:
            data["groups"].append(cid)
        elif ctype == "channel" and cid not in data["channels"]:
            data["channels"].append(cid)

        _save_chats(data)
    except:
        pass

# Broadcast function
async def _broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, pin_opt=False):
    username = update.effective_user.username if update.effective_user else None
    if username != BOT_OWNER_USERNAME:
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return

    text = None
    reply_msg = update.message.reply_to_message

    # If replying to a message, forward that
    if reply_msg:
        text = None  # We'll send the replied message itself
    else:
        if not context.args:
            await update.message.reply_text("Usage: /broadcast <message> or reply to a message.\nUse /broadcastpin to pin.")
            return
        text = " ".join(context.args).strip()

    chats = _load_chats()
    sent_users = sent_groups = sent_channels = 0

    for chat_type in ["users", "groups", "channels"]:
        for cid in list(chats[chat_type]):
            try:
                if reply_msg:
                    sent_msg = await reply_msg.copy(chat_id=cid)
                else:
                    sent_msg = await context.bot.send_message(chat_id=cid, text=text)

                if chat_type in ["groups", "channels"] and pin_opt:
                    try:
                        await context.bot.pin_chat_message(chat_id=cid, message_id=sent_msg.message_id, disable_notification=True)
                    except:
                        pass

                if chat_type == "users":
                    sent_users += 1
                elif chat_type == "groups":
                    sent_groups += 1
                elif chat_type == "channels":
                    sent_channels += 1
            except:
                pass

    total = sent_users + sent_groups + sent_channels
    await update.message.reply_text(
        f"✅ Broadcast finished.\n"
        f"👤 Users: {sent_users}\n"
        f"👥 Groups: {sent_groups}\n"
        f"📢 Channels: {sent_channels}\n"
        f"📊 Total delivered: {total}"
    )

# Commands
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _broadcast(update, context, pin_opt=False)

async def broadcast_pin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _broadcast(update, context, pin_opt=True)

# Export handlers
def get_handlers():
    return [
        CommandHandler("broadcast", broadcast_cmd),
        CommandHandler("broadcastpin", broadcast_pin_cmd),
        MessageHandler(filters.ALL, track_chat)
    ]

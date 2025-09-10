# utils/progress.py
import math
import asyncio
import time
from pyrogram.errors import FloodWait, MessageNotModified, MessageIdInvalid

async def progress_bar(current: int, total: int, message, prefix: str = "Downloading"):
    """
    Safe progress bar: edits message if still exists.
    """
    try:
        if total == 0:
            total = 1
        percent = (current / total) * 100
        filled = math.floor(percent / 5)
        if filled < 0: filled = 0
        if filled > 20: filled = 20
        bar = "█" * filled + "▒" * (20 - filled)
        text = f"{prefix}: {percent:.1f}%\n[{bar}]\n{current/1024/1024:.2f}MB / {total/1024/1024:.2f}MB"

        # basic existence check
        if getattr(message, "message_id", None) is None:
            return

        await message.edit_text(text)
    except FloodWait as e:
        await asyncio.sleep(getattr(e, "value", getattr(e, "retry_after", 1)))
        try:
            await message.edit_text(text)
        except:
            pass
    except (MessageNotModified, MessageIdInvalid):
        # message deleted / can't edit
        return
    except Exception:
        # ignore other edit errors
        return

async def progress_callback(current: int, total: int, message, prefix: str = "Downloading"):
    await progress_bar(current, total, message, prefix)

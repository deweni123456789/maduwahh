import os
import time
import io
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler

# Hugging Face API key
HUGGINGFACE_API_KEY = "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"

FALLBACK_MODELS = [
    "stabilityai/stable-diffusion-xl-base-1.0",
    "SG161222/Realistic_Vision_V5.1",
    "runwayml/stable-diffusion-v1-5"
]

MODEL_PRETTY_NAME = {
    "stabilityai/stable-diffusion-xl-base-1.0": "SDXL (1024×1024)",
    "SG161222/Realistic_Vision_V5.1": "Realistic Vision V5.1",
    "runwayml/stable-diffusion-v1-5": "Stable Diffusion v1.5"
}

MAX_MODEL_RETRIES = 3
REQUEST_TIMEOUT = 180
INITIAL_BACKOFF = 3


def is_image_bytes(b: bytes) -> bool:
    return b.startswith(b'\x89PNG') or b.startswith(b'\xff\xd8\xff')


async def try_generate_with_model(prompt: str, model: str):
    """Try generating an image with a specific model"""
    model_url = f"https://api-inference.huggingface.co/models/{model}"
    backoff = INITIAL_BACKOFF

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as session:
        for attempt in range(1, MAX_MODEL_RETRIES + 1):
            payload = {"inputs": prompt, "options": {"wait_for_model": True}}

            try:
                t0 = time.time()
                async with session.post(model_url, headers={"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}, json=payload) as resp:
                    elapsed = round(time.time() - t0, 2)
                    content_type = resp.headers.get("content-type", "")
                    data = await resp.read()

                    if resp.status == 200 and (content_type.startswith("image") or is_image_bytes(data)):
                        return data, elapsed, model, None

                    try:
                        j = await resp.json()
                    except Exception:
                        j = None

                    if resp.status in (429, 503, 504) or (j and "error" in j and ("loading" in j["error"].lower() or "busy" in j["error"].lower())):
                        if attempt < MAX_MODEL_RETRIES:
                            await asyncio.sleep(backoff)
                            backoff *= 2
                            continue
                        return None, None, None, f"Transient error: {str(j)}"

                    if j and "error" in j:
                        return None, None, None, f"Model error: {j['error']}"

                    return None, None, None, f"HTTP {resp.status} - {data[:200]}"

            except asyncio.TimeoutError:
                if attempt < MAX_MODEL_RETRIES:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                return None, None, None, f"Timeout after {REQUEST_TIMEOUT}s"
            except Exception as e:
                return None, None, None, f"Network error: {str(e)}"

    return None, None, None, f"Failed after {MAX_MODEL_RETRIES} attempts for {model}"


async def generate_image_with_fallbacks(prompt: str):
    """Try multiple models until success"""
    errors = []
    for model in FALLBACK_MODELS:
        img, elapsed, used_model, err = await try_generate_with_model(prompt, model)
        if img:
            return img, elapsed, used_model, None
        errors.append(f"{model}: {err}")
    return None, None, None, " | ".join(errors[:5])


async def get_image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram /image command handler"""
    if not context.args:
        await update.message.reply_text("❌ Please provide a prompt.\nUsage: `/image A realistic lion in the jungle`", parse_mode="Markdown")
        return

    prompt = " ".join(context.args)
    requester = f"@{update.effective_user.username}" if update.effective_user.username else (update.effective_user.first_name or "Unknown")

    info_msg = await update.message.reply_text(f"🎨 Generating: *{prompt}*\nPlease wait…", parse_mode="Markdown")

    image_bytes, gen_time, used_model, error = await generate_image_with_fallbacks(prompt)

    if image_bytes:
        file_obj = io.BytesIO(image_bytes)
        file_obj.name = "generated.png"

        caption = (
            f"🖼 Title: {prompt}\n"
            f"📏 Model: {MODEL_PRETTY_NAME.get(used_model, used_model)}\n"
            f"⏱ Time: {gen_time} sec\n"
            f"🙋 By: {requester}"
        )

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/deweni2")]])

        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=file_obj, caption=caption, reply_markup=keyboard)
        await info_msg.delete()
    else:
        await update.message.reply_text(f"⚠️ Failed to generate image.\nDetails: {error}")


def get_handler():
    """Return CommandHandler for main.py"""
    return CommandHandler("image", get_image_handler)

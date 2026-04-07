"""Telegram alert delivery tool."""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def _get_bot():
    import telegram
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")
    return telegram.Bot(token=BOT_TOKEN)


async def _send_async(message: str, chat_id: str = None):
    import telegram
    bot = _get_bot()
    target = chat_id or CHAT_ID
    if not target:
        raise ValueError("TELEGRAM_CHAT_ID not set")
    await bot.send_message(chat_id=target, text=message, parse_mode=telegram.constants.ParseMode.HTML)


def send_alert(message: str, chat_id: str = None):
    """Send a Telegram message. Falls back to dead-letter queue on failure."""
    import asyncio
    try:
        asyncio.run(_send_async(message, chat_id))
        log.info("Telegram sent: %s", message[:80])
        return True
    except Exception as exc:
        log.error("Telegram send failed: %s", exc)
        try:
            from src.database import save_dead_letter
            save_dead_letter(message, chat_id or CHAT_ID)
        except Exception:
            pass
        return False


def send_test():
    """Send a system-online test message."""
    return send_alert("✅ Stock Signal Bot is online and monitoring your portfolio.")


def retry_dead_letters():
    """Retry any messages stuck in the dead-letter queue."""
    try:
        from src.database import get_dead_letters, mark_dead_letter_retried, delete_dead_letter
        rows = get_dead_letters()
        for row in rows:
            ok = send_alert(row.message, row.chat_id)
            if ok:
                delete_dead_letter(row.id)
            else:
                mark_dead_letter_retried(row.id)
    except Exception as exc:
        log.error("Dead letter retry failed: %s", exc)

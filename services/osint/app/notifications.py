from typing import Optional, Dict
import httpx
from .config import settings


async def notify_telegram(message: str) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    data: Dict[str, str] = {
        "chat_id": settings.telegram_chat_id,
        "text": message,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": "true",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, data=data)
            return r.status_code == 200
    except Exception:
        return False



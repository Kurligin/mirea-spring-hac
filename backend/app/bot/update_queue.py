import asyncio
from typing import Any

# Глобальная очередь обновлений от MAX.
# Long-poll worker и webhook кладут сюда, dispatcher (P3b) заберёт.
update_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

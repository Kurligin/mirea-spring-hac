import asyncio
import logging

from app.bot.update_queue import update_queue
from app.core.max_client import MaxApiError, MaxClient


logger = logging.getLogger(__name__)


class LongPollWorker:
    """Опрашивает GET /updates в цикле и кладёт обновления в update_queue.

    Использовать только в dev (MAX_TRANSPORT=long_poll). В prod — webhook.
    """

    def __init__(
        self,
        client: MaxClient,
        *,
        poll_timeout: int = 30,
        sleep_on_empty: float = 1.0,
        types: list[str] | None = None,
    ):
        self.client = client
        self.poll_timeout = poll_timeout
        self.sleep_on_empty = sleep_on_empty
        self.types = types or [
            "message_created",
            "message_callback",
            "bot_started",
            "bot_stopped",
        ]
        self.marker: int | None = None
        self._stop = asyncio.Event()

    async def run_once(self) -> None:
        try:
            result = await self.client.get_updates(
                limit=100,
                timeout=self.poll_timeout,
                types=self.types,
                marker=self.marker,
            )
            updates = result.get("updates", [])
            new_marker = result.get("marker")
            if new_marker is not None:
                self.marker = new_marker
            for upd in updates:
                await update_queue.put(upd)
            if not updates:
                await asyncio.sleep(self.sleep_on_empty)
        except MaxApiError as e:
            logger.warning("long-poll error %s, sleeping", e)
            await asyncio.sleep(5)

    async def run(self) -> None:
        while not self._stop.is_set():
            await self.run_once()

    def stop(self) -> None:
        self._stop.set()

import asyncio

from httpx import ASGITransport

from app.bot.long_poll import LongPollWorker
from app.bot.update_queue import update_queue
from app.core.max_client import MaxClient
from tests.fixtures.mock_max import create_mock_max_app


async def test_long_poll_enqueues_updates_from_max():
    mock_app = create_mock_max_app()
    mock_app.state.mock["pending_updates"] = [
        {"update_type": "message_created", "message": {"text": "hi"}},
    ]

    # Drain queue from prior tests
    while not update_queue.empty():
        update_queue.get_nowait()

    transport = ASGITransport(app=mock_app)
    client = MaxClient(token="t", base_url="http://mock-max", transport=transport)
    worker = LongPollWorker(client, poll_timeout=1, sleep_on_empty=0.1)

    try:
        await asyncio.wait_for(worker.run_once(), timeout=5.0)
        result = await asyncio.wait_for(update_queue.get(), timeout=2.0)
        assert result["update_type"] == "message_created"
    finally:
        await client.close()

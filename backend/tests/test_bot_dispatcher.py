import asyncio

import pytest
from httpx import ASGITransport
from sqlalchemy import select

from app.bot.dispatcher import BotWorker, dispatch
from app.bot.update_queue import update_queue
from app.models.user import User
from tests.fixtures.bot_helpers import make_ctx, bot_stopped_update


async def test_dispatch_unknown_update_type_ignored(db):
    ctx, mock = make_ctx(db)
    await dispatch({"update_type": "some_future_event"}, ctx)
    assert mock.state.mock["sent_messages"] == []


async def test_dispatch_bot_stopped_marks_user_inactive(db):
    user = User(max_user_id=770001, is_active=True)
    db.add(user)
    await db.flush()
    ctx, _ = make_ctx(db)
    await dispatch(bot_stopped_update(770001), ctx)
    refreshed = (await db.execute(select(User).where(User.max_user_id == 770001))).scalar_one()
    assert refreshed.is_active is False


async def test_worker_swallows_handler_crash(db, monkeypatch):
    """Падение хендлера не валит воркер: ошибка логируется, обновление дропается."""
    from app.bot import dispatcher as disp

    async def boom(update, ctx):
        raise RuntimeError("handler exploded")

    monkeypatch.setattr(disp, "dispatch", boom)

    from app.core.db import AsyncSessionLocal
    from app.core.max_client import MaxClient
    from tests.fixtures.mock_max import create_mock_max_app

    transport = ASGITransport(app=create_mock_max_app())
    client = MaxClient(token="t", base_url="http://mock-max", transport=transport)
    worker = BotWorker(client, AsyncSessionLocal)

    while not update_queue.empty():
        update_queue.get_nowait()
    await update_queue.put({"update_type": "message_created", "message": {}})

    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0.2)
    assert not task.done()
    worker.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await client.close()

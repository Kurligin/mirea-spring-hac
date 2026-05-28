import asyncio
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.dispatcher import BotWorker
from app.bot.update_queue import update_queue
from app.core.max_client import MaxClient
from app.models.consent_log import ConsentKind
from app.models.event import Event, EventStatus, EventType
from app.models.event_field import EventField, FieldType
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User
from app.services.consent import ConsentService
from tests.fixtures.bot_helpers import callback_update, message_update
from tests.fixtures.mock_max import create_mock_max_app


async def test_worker_processes_full_registration_from_queue(test_engine):
    """BotWorker: rg → ввод поля → ok — запись создана, коммит прошёл."""
    SessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as setup:
        user = User(max_user_id=850001)
        event = Event(
            title="Интеграция", event_type=EventType.OPEN_DAY, status=EventStatus.PUBLISHED,
            starts_at=datetime.now(UTC) + timedelta(days=5), duration_minutes=60, capacity=10,
        )
        setup.add_all([user, event])
        await setup.flush()
        await ConsentService(setup).record(
            user_id=user.id, kind=ConsentKind.TERMS,
            doc_version=ConsentService.CURRENT_TERMS_VERSION,
        )
        setup.add(EventField(
            event_id=event.id, order=0, key="full_name", label="ФИО",
            field_type=FieldType.TEXT, required=True,
        ))
        await setup.commit()
        event_id = event.id
        user_id = user.id

    mock_app = create_mock_max_app()
    transport = ASGITransport(app=mock_app)
    client = MaxClient(token="t", base_url="http://mock-max", transport=transport)
    worker = BotWorker(client, SessionLocal)

    while not update_queue.empty():
        update_queue.get_nowait()

    task = asyncio.create_task(worker.run())
    try:
        await update_queue.put(callback_update(850001, f"rg:{event_id}"))
        await asyncio.sleep(0.15)
        await update_queue.put(message_update(850001, "Интеграл Интегралов"))
        await asyncio.sleep(0.15)
        await update_queue.put(callback_update(850001, f"ok:{event_id}"))
        await asyncio.sleep(0.25)
    finally:
        worker.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await client.close()

    async with SessionLocal() as check:
        reg = (await check.execute(
            select(Registration).where(
                Registration.user_id == user_id, Registration.event_id == event_id
            )
        )).scalar_one_or_none()
        assert reg is not None
        assert reg.status == RegistrationStatus.CONFIRMED
        assert reg.answers.get("full_name") == "Интеграл Интегралов"
        assert reg.short_code is not None

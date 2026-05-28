import asyncio
import logging

from fastapi import FastAPI

from app.api import calendar as public_calendar
from app.api import max_webhook
from app.api.admin import ad_broadcasts as admin_ad_broadcasts
from app.api.admin import audit as admin_audit
from app.api.admin import auth as admin_auth
from app.api.admin import broadcasts as admin_broadcasts
from app.api.admin import checkin as admin_checkin
from app.api.admin import controller as admin_controller
from app.api.admin import controller_home as admin_controller_home
from app.api.admin import event_controllers as admin_event_controllers
from app.api.admin import events as admin_events
from app.api.admin import fields as admin_fields
from app.api.admin import registrations as admin_regs
from app.api.admin import slots as admin_slots
from app.api.admin import stats as admin_stats
from app.api.admin import team as admin_team
from app.api.admin import uploads as admin_uploads
from app.bot.long_poll import LongPollWorker
from app.bot.qr_rotation import QrRotationWorker, qr_session_manager
from app.core.config import get_settings
from app.core.max_client import MaxClient

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """INFO-логи приложения (app.*) под uvicorn.

    Без этого у прикладных логгеров уровень WARNING (root по умолчанию),
    и INFO-строки бота — включая «bot update: …» — не видны в docker logs.
    """
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s"))
        app_logger.addHandler(handler)
    app_logger.propagate = False


_configure_logging()


def create_app() -> FastAPI:
    app = FastAPI(title="МАКС-2 Applicant Signup", version="0.1.0")
    app.include_router(admin_audit.router)
    app.include_router(admin_auth.router)
    app.include_router(admin_events.router)
    app.include_router(admin_fields.router)
    app.include_router(admin_regs.router)
    app.include_router(admin_slots.router)
    app.include_router(admin_stats.router)
    app.include_router(admin_team.router)
    app.include_router(admin_uploads.router)
    app.include_router(admin_checkin.router)
    app.include_router(admin_controller.router)
    app.include_router(admin_controller_home.router)
    app.include_router(admin_broadcasts.router)
    app.include_router(admin_ad_broadcasts.router)
    app.include_router(admin_event_controllers.router)
    app.include_router(max_webhook.router)
    app.include_router(public_calendar.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.on_event("startup")
    async def _start_bot() -> None:
        from app.bot.dispatcher import BotWorker
        from app.core.db import AsyncSessionLocal

        settings = get_settings()
        client = MaxClient(token=settings.max_bot_token, base_url=settings.max_api_base_url)
        app.state.bot_client = client

        worker = BotWorker(client, AsyncSessionLocal)
        app.state.bot_worker = worker
        app.state.bot_task = asyncio.create_task(worker.run())
        logger.info("Bot worker started")

        from app.services.scheduler import NotificationScheduler

        scheduler = NotificationScheduler(AsyncSessionLocal, client)
        scheduler.start()
        app.state.notification_scheduler = scheduler

        qr_worker = QrRotationWorker(
            client=client,
            session_factory=AsyncSessionLocal,
            manager=qr_session_manager,
        )
        app.state.qr_worker = qr_worker
        app.state.qr_worker_task = asyncio.create_task(qr_worker.run())
        logger.info("QR rotation worker started")

        if settings.max_transport == "long_poll":
            lp = LongPollWorker(client)
            app.state.long_poll_worker = lp
            app.state.long_poll_task = asyncio.create_task(lp.run())
            logger.info("Long-poll worker started (dev mode)")

    @app.on_event("shutdown")
    async def _stop_bot() -> None:
        scheduler = getattr(app.state, "notification_scheduler", None)
        if scheduler is not None:
            scheduler.shutdown()
        for worker_attr in ("bot_worker", "long_poll_worker", "qr_worker"):
            w = getattr(app.state, worker_attr, None)
            if w is not None:
                w.stop()
        for task_attr in ("bot_task", "long_poll_task", "qr_worker_task"):
            t = getattr(app.state, task_attr, None)
            if t is not None:
                t.cancel()
        client = getattr(app.state, "bot_client", None)
        if client is not None:
            await client.close()

    return app


app = create_app()

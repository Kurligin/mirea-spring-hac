"""Хелперы для тестов бота: билдеры обновлений MAX + сборка BotContext."""
from __future__ import annotations

from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.context import BotContext
from app.core.max_client import MaxClient
from tests.fixtures.mock_max import create_mock_max_app


def make_ctx(db: AsyncSession) -> tuple[BotContext, object]:
    """Возвращает (BotContext, mock_app). mock_app.state.mock — записанные вызовы."""
    mock_app = create_mock_max_app()
    transport = ASGITransport(app=mock_app)
    client = MaxClient(token="test", base_url="http://mock-max", transport=transport)
    return BotContext(client, db), mock_app


def bot_started_update(user_id: int, *, first_name: str = "Тест", chat_id: int | None = None) -> dict:
    return {
        "update_type": "bot_started",
        "chat_id": chat_id if chat_id is not None else user_id,
        "user": {"user_id": user_id, "first_name": first_name, "name": first_name},
    }


def bot_stopped_update(user_id: int, *, chat_id: int | None = None) -> dict:
    return {
        "update_type": "bot_stopped",
        "chat_id": chat_id if chat_id is not None else user_id,
        "user": {"user_id": user_id},
    }


def message_update(
    user_id: int,
    text: str = "",
    *,
    chat_id: int | None = None,
    attachments: list[dict] | None = None,
) -> dict:
    return {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": user_id, "first_name": "Тест"},
            "recipient": {"chat_id": chat_id if chat_id is not None else user_id, "chat_type": "dialog"},
            "body": {"mid": "m1", "seq": 1, "text": text, "attachments": attachments or []},
        },
    }


def callback_update(
    user_id: int,
    payload: str,
    *,
    callback_id: str = "cb-1",
    chat_id: int | None = None,
) -> dict:
    return {
        "update_type": "message_callback",
        "callback": {
            "callback_id": callback_id,
            "payload": payload,
            "user": {"user_id": user_id, "first_name": "Тест"},
        },
        "message": {
            "recipient": {"chat_id": chat_id if chat_id is not None else user_id, "chat_type": "dialog"},
            "body": {"mid": "m1", "seq": 1, "text": "", "attachments": []},
        },
    }


def sent_texts(mock_app) -> list[str]:
    return [m["body"].get("text", "") for m in mock_app.state.mock["sent_messages"]]


def answer_texts(mock_app) -> list[str]:
    out = []
    for a in mock_app.state.mock["answers"]:
        msg = a["body"].get("message")
        if msg:
            out.append(msg.get("text", ""))
    return out

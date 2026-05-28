"""BotContext — окружение обработки одного обновления MAX."""
from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.max_client import MaxClient
from app.models.user import User

_KEYBOARD_ATTACHMENT = "inline_keyboard"


class BotContext:
    """MaxClient + БД-сессия + хелперы. Создаётся на каждое обновление."""

    def __init__(self, client: MaxClient, db: AsyncSession):
        self.client = client
        self.db = db

    async def get_or_create_user(
        self,
        max_user_id: int,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        username: str | None = None,
    ) -> User:
        user = (
            await self.db.execute(select(User).where(User.max_user_id == max_user_id))
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        if user is None:
            user = User(
                max_user_id=max_user_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                last_seen_at=now,
            )
            self.db.add(user)
            await self.db.flush()
            return user
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if username:
            user.username = username
        user.last_seen_at = now
        if not user.is_active:
            user.is_active = True
        await self.db.flush()
        return user

    async def send(
        self,
        chat_id: int,
        text: str,
        keyboard: list[list[dict]] | None = None,
    ) -> dict:
        return await self.client.send_message(chat_id=chat_id, text=text, keyboard=keyboard)

    async def edit(
        self,
        callback_id: str,
        text: str,
        keyboard: list[list[dict]] | None = None,
        *,
        notification: str | None = None,
    ) -> dict:
        """In-place правка сообщения, на котором нажали callback-кнопку."""
        body: dict = {"text": text}
        if keyboard is not None:
            body["attachments"] = [
                {"type": _KEYBOARD_ATTACHMENT, "payload": {"buttons": keyboard}}
            ]
        return await self.client.answer_callback(
            callback_id=callback_id, notification=notification, message=body
        )

    async def toast(self, callback_id: str, text: str) -> dict:
        """Короткое всплывающее уведомление без правки сообщения."""
        return await self.client.answer_callback(callback_id=callback_id, notification=text)


def extract_phone_from_contact(attachments: list[dict]) -> str | None:
    """Достаёт телефон из contact-вложения message_created (vCard TEL-строка)."""
    for att in attachments or []:
        if att.get("type") != "contact":
            continue
        vcf = (att.get("payload") or {}).get("vcf_info") or ""
        m = re.search(r"TEL[^:]*:([+0-9()\-\s]+)", vcf)
        if m:
            digits = re.sub(r"[^\d+]", "", m.group(1))
            if digits:
                return digits
    return None

import asyncio
import logging
from typing import Any

import httpx

from app.core.rate_limiter import TokenBucket


logger = logging.getLogger(__name__)


class MaxApiError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"MAX API {status}: {message}")


class MaxUserBlocked(MaxApiError):
    """Юзер заблокировал бота / удалил профиль."""


class MaxRateLimited(MaxApiError):
    """429 от MAX. Внутренний лимитер должен такое предотвращать."""


class MaxClient:
    """Обёртка над MAX Bot API.

    Все исходящие вызовы идут через rate-limiter (30 rps).
    Retry с exp backoff на 5xx/timeout, до 3 попыток.
    """

    def __init__(
        self,
        *,
        token: str,
        base_url: str = "https://platform-api.max.ru",
        transport: httpx.AsyncBaseTransport | None = None,
        rate: float = 30.0,
        rate_capacity: int = 30,
        timeout: float = 15.0,
    ):
        self.token = token
        self.base_url = base_url
        self._limiter = TokenBucket(rate=rate, capacity=rate_capacity)
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": token},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: Any = None,
        content: bytes | None = None,
        timeout: float | None = None,
    ) -> dict:
        await self._limiter.acquire()
        last_exc: Exception | None = None
        req_kwargs: dict[str, Any] = {"params": params, "json": json, "content": content}
        if timeout is not None:
            req_kwargs["timeout"] = timeout
        for attempt in range(3):
            try:
                resp = await self._client.request(method, path, **req_kwargs)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
                last_exc = e
                await asyncio.sleep(2**attempt)
                continue
            if resp.status_code >= 500:
                await asyncio.sleep(2**attempt)
                continue
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", "1"))
                await asyncio.sleep(retry_after)
                continue
            if resp.status_code == 403:
                raise MaxUserBlocked(403, "Bot blocked or chat not accessible")
            if resp.status_code >= 400:
                raise MaxApiError(resp.status_code, resp.text)
            return resp.json()
        if last_exc:
            raise MaxApiError(0, f"network error after retries: {last_exc}")
        raise MaxApiError(0, "exhausted retries on 5xx/429")

    async def get_me(self) -> dict:
        return await self._request("GET", "/me")

    async def send_message(
        self,
        *,
        user_id: int | None = None,
        chat_id: int | None = None,
        text: str,
        keyboard: list[list[dict]] | None = None,
        attachments: list[dict] | None = None,
        notify: bool = True,
        format: str | None = None,
    ) -> dict:
        if (user_id is None) == (chat_id is None):
            raise ValueError("Specify exactly one of user_id, chat_id")
        body: dict[str, Any] = {"text": text, "notify": notify}
        att: list[dict] = []
        if attachments:
            att.extend(attachments)
        if keyboard is not None:
            att.append({"type": "inline_keyboard", "payload": {"buttons": keyboard}})
        if att:
            body["attachments"] = att
        if format:
            body["format"] = format
        params = {"user_id": user_id} if user_id is not None else {"chat_id": chat_id}
        return await self._request("POST", "/messages", params=params, json=body)

    async def edit_message(
        self,
        *,
        message_id: str,
        text: str | None = None,
        keyboard: list[list[dict]] | None = None,
        attachments: list[dict] | None = None,
    ) -> dict:
        """PUT /messages?message_id= — правит уже отправленное сообщение (моложе 24ч).

        attachments=None и keyboard=None → вложения не меняются (поле опущено).
        attachments=[] → все вложения удаляются.
        attachments=[...] → заменяются (плюс при keyboard добавляется ряд кнопок).
        """
        body: dict[str, Any] = {}
        if text is not None:
            body["text"] = text
        att: list[dict] | None = None
        if attachments is not None:
            att = list(attachments)
        if keyboard is not None:
            if att is None:
                att = []
            att.append({"type": "inline_keyboard", "payload": {"buttons": keyboard}})
        if att is not None:
            body["attachments"] = att
        return await self._request("PUT", "/messages", params={"message_id": message_id}, json=body)

    async def answer_callback(
        self,
        *,
        callback_id: str,
        notification: str | None = None,
        message: dict | None = None,
    ) -> dict:
        body: dict[str, Any] = {}
        if notification:
            body["notification"] = notification
        if message:
            body["message"] = message
        return await self._request("POST", "/answers", params={"callback_id": callback_id}, json=body)

    async def upload_file(self, *, data: bytes, kind: str) -> dict:
        return await self._request("POST", "/uploads", params={"type": kind}, content=data)

    async def upload_image_for_attachment(self, *, data: bytes) -> dict:
        """Двухшаговый MAX-upload: POST /uploads?type=image → upload URL →
        POST на URL с байтами → token. Возвращает готовое attachment-описание
        для вложения в send_message/edit_message: {type:'image', payload:{token}}.
        """
        init = await self._request("POST", "/uploads", params={"type": "image"})
        upload_url = init.get("url") if isinstance(init, dict) else None
        if not upload_url:
            raise MaxApiError(0, f"upload init: no url in response: {init!r}")
        files = {"data": ("qr.png", data, "image/png")}
        resp = await self._client.post(upload_url, files=files)
        if resp.status_code >= 400:
            raise MaxApiError(resp.status_code, resp.text)
        body = resp.json()
        token: str | None = None
        if isinstance(body, dict):
            token = body.get("token")
            if not token:
                photos = body.get("photos")
                if isinstance(photos, dict) and photos:
                    first = next(iter(photos.values()))
                    if isinstance(first, dict):
                        token = first.get("token")
        if not token:
            raise MaxApiError(0, f"upload finalize: no token in response: {body!r}")
        return {"type": "image", "payload": {"token": token}}

    async def typing_on(self, *, chat_id: int) -> dict:
        return await self._request(
            "POST", f"/chats/{chat_id}/actions", json={"action": "typing_on"}
        )

    async def get_updates(
        self,
        *,
        limit: int = 100,
        timeout: int = 30,
        types: list[str] | None = None,
        marker: int | None = None,
    ) -> dict:
        params: dict[str, Any] = {"limit": limit, "timeout": timeout}
        if types:
            params["types"] = ",".join(types)
        if marker:
            params["marker"] = marker
        # MAX держит /updates до `timeout` секунд — httpx-таймаут запроса
        # должен быть заметно больше серверного long-poll окна.
        return await self._request("GET", "/updates", params=params, timeout=timeout + 15)

    async def set_webhook(self, *, url: str, secret: str | None = None) -> dict:
        body: dict[str, Any] = {"url": url}
        if secret:
            body["secret"] = secret
        return await self._request("POST", "/subscriptions", json=body)

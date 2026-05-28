"""Отправка рекламной рассылки (AdCampaign) всем пользователям бота."""
from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.max_client import MaxClient
from app.models.ad_campaign import AdCampaign, AdCampaignStatus
from app.models.user import User

logger = logging.getLogger(__name__)


class AdBroadcastService:
    def __init__(self, db: AsyncSession, client: MaxClient):
        self.db = db
        self.client = client

    async def _image_attachment(self, campaign: AdCampaign) -> list[dict] | None:
        if not campaign.image_path:
            return None
        try:
            base = os.path.realpath(get_settings().upload_dir)
            path = os.path.realpath(os.path.join(base, campaign.image_path))
            # защита от path traversal: путь обязан остаться внутри upload_dir
            if path != base and not path.startswith(base + os.sep):
                logger.warning(
                    "ad campaign %s: image_path вне upload_dir (%r) — пропускаю фото",
                    campaign.id, campaign.image_path,
                )
                return None
            with open(path, "rb") as f:
                data = f.read()
            att = await self.client.upload_image_for_attachment(data=data)
            return [att]
        except Exception:
            logger.exception("ad campaign %s: image upload failed, отправляю без фото", campaign.id)
            return None

    async def send(self, campaign: AdCampaign) -> dict[str, int]:
        """Разослать кампанию всем пользователям. Идемпотентно по статусу не защищено —
        вызывать один раз (из API send_now или планировщика для SCHEDULED)."""
        campaign.status = AdCampaignStatus.SENDING
        await self.db.flush()

        users = list((await self.db.execute(select(User))).scalars().all())
        text = f"{campaign.title}\n\n{campaign.body}" if campaign.body else campaign.title
        attachments = await self._image_attachment(campaign)

        delivered = 0
        errors = 0
        for user in users:
            try:
                await self.client.send_message(
                    user_id=user.max_user_id, text=text, attachments=attachments
                )
                delivered += 1
            except Exception:
                logger.exception("ad campaign %s: ошибка отправки user=%s", campaign.id, user.max_user_id)
                errors += 1

        campaign.recipients_total = len(users)
        campaign.delivered = delivered
        campaign.errors = errors
        campaign.status = AdCampaignStatus.SENT
        campaign.sent_at = datetime.now(UTC)
        await self.db.flush()
        logger.info(
            "ad campaign %s отправлена: всего=%d доставлено=%d ошибок=%d",
            campaign.id, len(users), delivered, errors,
        )
        return {"recipients": len(users), "delivered": delivered, "errors": errors}

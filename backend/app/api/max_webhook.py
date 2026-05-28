from fastapi import APIRouter, Header, HTTPException, Request, status

from app.bot.update_queue import update_queue
from app.core.config import get_settings

router = APIRouter(tags=["max-webhook"])


@router.post("/max/webhook")
async def receive_update(
    request: Request,
    x_max_bot_api_secret: str | None = Header(default=None, alias="X-Max-Bot-Api-Secret"),
) -> dict[str, str]:
    settings = get_settings()
    if x_max_bot_api_secret != settings.webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    payload = await request.json()
    await update_queue.put(payload)
    return {"status": "accepted"}

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_admin, get_db
from app.models.admin_account import AdminAccount
from app.models.media_file import MediaKind
from app.services.media import MediaService, UnsupportedMimeError

router = APIRouter(prefix="/api/admin/uploads", tags=["admin-uploads"])


class MediaUploadResponse(BaseModel):
    id: str
    kind: MediaKind
    path: str
    url: str
    mime: str
    size: int
    width: int | None
    height: int | None


@router.post("", response_model=MediaUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    kind: MediaKind = Query(...),
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    settings = get_settings()
    data = await file.read()
    if len(data) > settings.upload_max_bytes:
        raise HTTPException(413, f"File too large (max {settings.upload_max_bytes // 1024 // 1024} MB)")
    try:
        media = await MediaService(db).upload(
            uploader_id=admin.id, kind=kind, filename=file.filename or "unnamed", data=data
        )
    except UnsupportedMimeError as e:
        raise HTTPException(415, str(e)) from e
    await db.commit()
    return MediaUploadResponse(
        id=str(media.id), kind=media.kind, path=media.path, url=f"/media/{media.path}",
        mime=media.mime, size=media.size, width=media.width, height=media.height,
    )

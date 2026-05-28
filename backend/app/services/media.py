import hashlib
import io
import uuid
from pathlib import Path
from uuid import UUID

import magic
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.media_file import MediaFile, MediaKind


ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class UnsupportedMimeError(Exception):
    pass


class MediaService:
    def __init__(self, db: AsyncSession, root: str | None = None):
        self.db = db
        self.root = Path(root or get_settings().upload_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    async def upload(
        self,
        *,
        uploader_id: UUID,
        kind: MediaKind,
        filename: str,
        data: bytes,
        event_id: UUID | None = None,
    ) -> MediaFile:
        mime = magic.from_buffer(data, mime=True)
        if mime not in ALLOWED_MIMES:
            raise UnsupportedMimeError(f"MIME {mime} не поддерживается")

        sha = hashlib.sha256(data).digest()
        existing = (
            await self.db.execute(select(MediaFile).where(MediaFile.sha256 == sha))
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        ext = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }[mime]
        rel_dir = Path(kind.value)
        if event_id:
            rel_dir = rel_dir / str(event_id)
        full_dir = self.root / rel_dir
        full_dir.mkdir(parents=True, exist_ok=True)
        rel_path = rel_dir / f"{uuid.uuid4().hex}{ext}"
        abs_path = self.root / rel_path
        abs_path.write_bytes(data)

        width = height = None
        try:
            with Image.open(io.BytesIO(data)) as im:
                width, height = im.size
        except Exception:
            pass

        media = MediaFile(
            kind=kind,
            event_id=event_id,
            uploader_id=uploader_id,
            path=str(rel_path),
            mime=mime,
            size=len(data),
            width=width,
            height=height,
            sha256=sha,
        )
        self.db.add(media)
        await self.db.flush()
        return media

    async def get(self, media_id: UUID) -> MediaFile | None:
        return (
            await self.db.execute(select(MediaFile).where(MediaFile.id == media_id))
        ).scalar_one_or_none()

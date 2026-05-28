from uuid import UUID

from pydantic import BaseModel

from app.models.media_file import MediaKind


class MediaResponse(BaseModel):
    id: UUID
    kind: MediaKind
    path: str
    url: str
    mime: str
    size: int
    width: int | None
    height: int | None

    class Config:
        from_attributes = True

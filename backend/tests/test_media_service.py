import pytest

from app.models.media_file import MediaKind
from app.services.media import MediaService, UnsupportedMimeError
from tests.factories import AdminAccountFactory


# Minimal valid JPEG bytes (SOI + APP0 + DQT marker + EOI)
JPEG_BYTES = (
    bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300080606"
        "07060805070707090908"
    )
    + b"\x00" * 1000
    + bytes.fromhex("ffd9")
)


async def test_upload_creates_file_and_db_row(db, tmp_path):
    admin = AdminAccountFactory()
    db.add(admin)
    await db.flush()

    svc = MediaService(db, root=str(tmp_path))
    media = await svc.upload(
        uploader_id=admin.id,
        kind=MediaKind.EVENT_COVER,
        filename="cover.jpg",
        data=JPEG_BYTES,
    )
    assert media.id is not None
    assert (tmp_path / media.path).exists()
    assert media.mime.startswith("image/")


async def test_upload_dedup_returns_same_row_for_same_content(db, tmp_path):
    admin = AdminAccountFactory()
    db.add(admin)
    await db.flush()

    svc = MediaService(db, root=str(tmp_path))
    m1 = await svc.upload(uploader_id=admin.id, kind=MediaKind.EVENT_COVER, filename="a.jpg", data=JPEG_BYTES)
    m2 = await svc.upload(uploader_id=admin.id, kind=MediaKind.EVENT_COVER, filename="b.jpg", data=JPEG_BYTES)
    assert m1.id == m2.id


async def test_upload_rejects_invalid_mime(db, tmp_path):
    admin = AdminAccountFactory()
    db.add(admin)
    await db.flush()
    svc = MediaService(db, root=str(tmp_path))
    with pytest.raises(UnsupportedMimeError):
        await svc.upload(uploader_id=admin.id, kind=MediaKind.EVENT_COVER, filename="x.exe", data=b"not-image")

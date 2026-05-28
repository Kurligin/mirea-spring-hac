from app.models.admin_account import AdminAccount, AdminRole
from app.models.media_file import MediaFile, MediaKind


async def test_media_file_persisted(db):
    admin = AdminAccount(email="media-model@test.local", password_hash="x", role=AdminRole.SUPER)
    db.add(admin)
    await db.flush()
    media = MediaFile(
        kind=MediaKind.EVENT_COVER,
        uploader_id=admin.id,
        path="events/abc/cover.jpg",
        mime="image/jpeg",
        size=12345,
        width=1920,
        height=1080,
        sha256=b"x" * 32,
    )
    db.add(media)
    await db.flush()
    assert media.id is not None
    assert media.kind == MediaKind.EVENT_COVER

from app.models.consent_log import ConsentKind
from app.models.user import User
from app.services.consent import ConsentService


async def test_record_consent_and_status(db):
    u = User(max_user_id=55001); db.add(u); await db.flush()
    svc = ConsentService(db)
    await svc.record(user_id=u.id, kind=ConsentKind.TERMS, doc_version="v1.0", ip="127.0.0.1", user_agent="test")
    status = await svc.status(u.id)
    assert status[ConsentKind.TERMS] == "v1.0"
    assert ConsentKind.PHONE not in status


async def test_status_returns_latest_version(db):
    u = User(max_user_id=55002); db.add(u); await db.flush()
    svc = ConsentService(db)
    await svc.record(user_id=u.id, kind=ConsentKind.TERMS, doc_version="v1.0")
    await svc.record(user_id=u.id, kind=ConsentKind.TERMS, doc_version="v1.1")
    status = await svc.status(u.id)
    assert status[ConsentKind.TERMS] == "v1.1"


async def test_has_accepted_terms_current_version(db):
    u = User(max_user_id=55003); db.add(u); await db.flush()
    svc = ConsentService(db)
    assert await svc.has_accepted_terms(u.id) is False
    await svc.record(user_id=u.id, kind=ConsentKind.TERMS, doc_version=svc.CURRENT_TERMS_VERSION)
    assert await svc.has_accepted_terms(u.id) is True


async def test_has_accepted_terms_outdated_version(db):
    u = User(max_user_id=55004); db.add(u); await db.flush()
    svc = ConsentService(db)
    await svc.record(user_id=u.id, kind=ConsentKind.TERMS, doc_version="v0.9")  # outdated
    assert await svc.has_accepted_terms(u.id) is False

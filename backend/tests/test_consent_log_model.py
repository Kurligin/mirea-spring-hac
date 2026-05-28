from app.models.consent_log import ConsentKind, ConsentLog
from app.models.user import User


async def test_consent_log_persisted(db):
    u = User(max_user_id=77001); db.add(u); await db.flush()
    log = ConsentLog(
        user_id=u.id,
        doc_kind=ConsentKind.TERMS,
        doc_version="v1.0",
        ip="127.0.0.1",
        user_agent="Mozilla/5.0",
    )
    db.add(log); await db.flush()
    assert log.id is not None
    assert log.doc_kind == ConsentKind.TERMS
    assert log.doc_version == "v1.0"


async def test_consent_log_phone_kind(db):
    u = User(max_user_id=77002); db.add(u); await db.flush()
    log = ConsentLog(user_id=u.id, doc_kind=ConsentKind.PHONE, doc_version="v1.0")
    db.add(log); await db.flush()
    assert log.doc_kind == ConsentKind.PHONE
    assert log.ip is None

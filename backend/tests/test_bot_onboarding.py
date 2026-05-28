from sqlalchemy import select

from app.bot.dispatcher import dispatch
from app.models.consent_log import ConsentKind, ConsentLog
from app.models.user import User
from app.services.consent import ConsentService
from tests.fixtures.bot_helpers import (
    answer_texts, bot_started_update, callback_update, make_ctx,
    message_update, sent_texts,
)


async def test_bot_started_new_user_shows_disclaimer(db):
    ctx, mock = make_ctx(db)
    await dispatch(bot_started_update(810001, first_name="Аня"), ctx)
    texts = sent_texts(mock)
    # Дисклеймер по формулировкам кейса 2: «не официальная функция платформы МАКС».
    assert any("не является официальной функцией платформы МАКС" in t for t in texts)
    # Согласие — на «идентификатор пользователя и отображаемое имя» (а не «ФИО, контакты»).
    assert any("идентификатора пользователя" in t for t in texts)
    buttons = mock.state.mock["sent_messages"][-1]["body"]["attachments"][0]["payload"]["buttons"]
    payloads = [b["payload"] for row in buttons for b in row if b["type"] == "callback"]
    assert "terms" in payloads


async def test_bot_started_creates_user(db):
    ctx, _ = make_ctx(db)
    await dispatch(bot_started_update(810002, first_name="Боря"), ctx)
    user = (await db.execute(select(User).where(User.max_user_id == 810002))).scalar_one()
    assert user.first_name == "Боря"


async def test_terms_callback_records_consent_and_shows_menu(db):
    ctx, mock = make_ctx(db)
    await dispatch(bot_started_update(810003), ctx)
    await dispatch(callback_update(810003, "terms"), ctx)

    user = (await db.execute(select(User).where(User.max_user_id == 810003))).scalar_one()
    logs = (
        await db.execute(select(ConsentLog).where(ConsentLog.user_id == user.id))
    ).scalars().all()
    assert any(log.doc_kind == ConsentKind.TERMS for log in logs)
    assert any("меню" in t.lower() for t in answer_texts(mock))


async def test_bot_started_with_consent_shows_menu_directly(db):
    user = User(max_user_id=810004)
    db.add(user)
    await db.flush()
    await ConsentService(db).record(
        user_id=user.id, kind=ConsentKind.TERMS, doc_version=ConsentService.CURRENT_TERMS_VERSION
    )
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(bot_started_update(810004), ctx)
    texts = sent_texts(mock)
    assert any("меню" in t.lower() for t in texts)
    assert not any("не является официальным каналом" in t for t in texts)


async def test_bot_stopped_marks_inactive(db):
    user = User(max_user_id=810005, is_active=True)
    db.add(user)
    await db.flush()
    ctx, _ = make_ctx(db)
    from tests.fixtures.bot_helpers import bot_stopped_update
    await dispatch(bot_stopped_update(810005), ctx)
    refreshed = (await db.execute(select(User).where(User.max_user_id == 810005))).scalar_one()
    assert refreshed.is_active is False


async def test_fallback_message_shows_menu(db):
    # юзер с принятыми условиями → произвольное сообщение ведёт в меню
    user = User(max_user_id=810006)
    db.add(user)
    await db.flush()
    await ConsentService(db).record(
        user_id=user.id, kind=ConsentKind.TERMS, doc_version=ConsentService.CURRENT_TERMS_VERSION
    )
    await db.flush()
    ctx, mock = make_ctx(db)
    await dispatch(message_update(810006, "привет"), ctx)
    assert any("меню" in t.lower() for t in sent_texts(mock))

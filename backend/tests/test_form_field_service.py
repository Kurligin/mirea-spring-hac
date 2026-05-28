import pytest

from app.models.event_field import FieldType
from app.schemas.event_field import EventFieldCreate
from app.services.form_field import FormFieldService, ValidationError
from tests.factories import EventFactory, EventFieldFactory


async def test_create_field_assigns_id(db):
    event = EventFactory()
    db.add(event)
    await db.flush()

    service = FormFieldService(db)
    payload = EventFieldCreate(key="full_name", label="ФИО", field_type=FieldType.TEXT, required=True)
    field = await service.create(event.id, payload)
    assert field.id is not None


async def test_validate_required_text_missing_raises(db):
    event = EventFactory()
    db.add(event)
    await db.flush()
    fld = EventFieldFactory(event_id=event.id, key="full_name", field_type=FieldType.TEXT, required=True)
    db.add(fld)
    await db.flush()

    service = FormFieldService(db)
    with pytest.raises(ValidationError):
        await service.validate_answers(event.id, {})


async def test_validate_optional_missing_ok(db):
    event = EventFactory()
    db.add(event)
    await db.flush()
    fld = EventFieldFactory(event_id=event.id, key="comment", field_type=FieldType.TEXT, required=False)
    db.add(fld)
    await db.flush()

    service = FormFieldService(db)
    result = await service.validate_answers(event.id, {})
    assert result == {}


async def test_validate_email_format_invalid_raises(db):
    event = EventFactory()
    db.add(event)
    await db.flush()
    fld = EventFieldFactory(event_id=event.id, key="email", field_type=FieldType.EMAIL, required=True)
    db.add(fld)
    await db.flush()

    service = FormFieldService(db)
    with pytest.raises(ValidationError):
        await service.validate_answers(event.id, {"email": "not-an-email"})


async def test_validate_select_unknown_option_raises(db):
    event = EventFactory()
    db.add(event)
    await db.flush()
    fld = EventFieldFactory(
        event_id=event.id,
        key="track",
        field_type=FieldType.SELECT,
        required=True,
        options=[{"value": "it", "label": "ИТ"}, {"value": "math", "label": "Математика"}],
    )
    db.add(fld)
    await db.flush()

    service = FormFieldService(db)
    with pytest.raises(ValidationError):
        await service.validate_answers(event.id, {"track": "unknown"})

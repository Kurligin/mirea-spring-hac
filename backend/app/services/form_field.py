import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_field import EventField, FieldType
from app.schemas.event_field import EventFieldCreate


class ValidationError(Exception):
    def __init__(self, field_key: str, message: str):
        self.field_key = field_key
        self.message = message
        super().__init__(f"{field_key}: {message}")


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?\d{10,15}$")


class FormFieldService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_event(self, event_id: UUID) -> list[EventField]:
        stmt = select(EventField).where(EventField.event_id == event_id).order_by(EventField.order)
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(self, event_id: UUID, payload: EventFieldCreate) -> EventField:
        data = payload.model_dump()
        if data.get("options"):
            data["options"] = [o for o in data["options"]]
        field = EventField(event_id=event_id, **data)
        self.db.add(field)
        await self.db.flush()
        return field

    async def replace_all(self, event_id: UUID, payloads: list[EventFieldCreate]) -> list[EventField]:
        existing = await self.list_for_event(event_id)
        for f in existing:
            await self.db.delete(f)
        await self.db.flush()
        result = []
        for i, p in enumerate(payloads):
            data = p.model_dump()
            data["order"] = i
            if data.get("options"):
                data["options"] = [o for o in data["options"]]
            f = EventField(event_id=event_id, **data)
            self.db.add(f)
            result.append(f)
        await self.db.flush()
        return result

    async def validate_answers(self, event_id: UUID, answers: dict[str, Any]) -> dict[str, Any]:
        fields = await self.list_for_event(event_id)
        cleaned: dict[str, Any] = {}
        for fld in fields:
            value = answers.get(fld.key)
            if value is None or value == "":
                if fld.required:
                    raise ValidationError(fld.key, "обязательное поле")
                continue
            cleaned[fld.key] = self._coerce_and_validate(fld, value)
        return cleaned

    def validate_value(self, field: EventField, value: Any) -> Any:
        """Валидирует одно значение поля (для пошагового ввода в боте).

        None/'' для required → ValidationError; иначе coerce по типу.
        """
        if value is None or value == "":
            if field.required:
                raise ValidationError(field.key, "обязательное поле")
            return None
        return self._coerce_and_validate(field, value)

    def _coerce_and_validate(self, fld: EventField, value: Any) -> Any:
        if fld.field_type == FieldType.EMAIL:
            if not isinstance(value, str) or not _EMAIL_RE.match(value):
                raise ValidationError(fld.key, "невалидный email")
            return value.lower()
        if fld.field_type == FieldType.PHONE:
            if not isinstance(value, str) or not _PHONE_RE.match(value):
                raise ValidationError(fld.key, "невалидный телефон")
            return value
        if fld.field_type == FieldType.NUMBER:
            try:
                return float(value)
            except (TypeError, ValueError) as e:
                raise ValidationError(fld.key, "не число") from e
        if fld.field_type in (FieldType.TEXT, FieldType.TEXTAREA):
            if not isinstance(value, str):
                raise ValidationError(fld.key, "не строка")
            return value
        if fld.field_type == FieldType.SELECT:
            allowed = [o["value"] for o in (fld.options or [])]
            if value not in allowed:
                raise ValidationError(fld.key, "значение вне списка")
            return value
        if fld.field_type == FieldType.MULTI_SELECT:
            if not isinstance(value, list):
                raise ValidationError(fld.key, "ожидается список")
            allowed = [o["value"] for o in (fld.options or [])]
            for v in value:
                if v not in allowed:
                    raise ValidationError(fld.key, f"значение '{v}' вне списка")
            return value
        if fld.field_type == FieldType.CONSENT:
            if not value:
                raise ValidationError(fld.key, "требуется согласие")
            return True
        return value

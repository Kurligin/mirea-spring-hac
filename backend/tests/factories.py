from datetime import UTC, datetime, timedelta

import factory

from app.models.admin_account import AdminAccount, AdminRole
from app.models.event import Event, EventStatus, EventType
from app.models.event_field import EventField, FieldType
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User


class AdminAccountFactory(factory.Factory):
    class Meta:
        model = AdminAccount

    email = factory.Sequence(lambda n: f"admin{n}@mirea.ru")
    password_hash = "$2b$12$placeholder"
    role = AdminRole.SUPER
    full_name = factory.Faker("name", locale="ru_RU")


class UserFactory(factory.Factory):
    class Meta:
        model = User

    max_user_id = factory.Sequence(lambda n: 100000 + n)
    username = factory.Sequence(lambda n: f"user{n}")
    first_name = factory.Faker("first_name", locale="ru_RU")
    last_name = factory.Faker("last_name", locale="ru_RU")


class EventFactory(factory.Factory):
    class Meta:
        model = Event

    title = factory.Faker("sentence", nb_words=3, locale="ru_RU")
    description = factory.Faker("paragraph", locale="ru_RU")
    event_type = EventType.OPEN_DAY
    status = EventStatus.PUBLISHED
    starts_at = factory.LazyFunction(lambda: datetime.now(UTC) + timedelta(days=7))
    duration_minutes = 120
    capacity = 50
    waitlist_enabled = True
    reminder_offsets_minutes = factory.LazyFunction(lambda: [1440, 60])


class EventFieldFactory(factory.Factory):
    class Meta:
        model = EventField

    order = 0
    key = factory.Sequence(lambda n: f"field_{n}")
    label = factory.Faker("sentence", nb_words=2, locale="ru_RU")
    field_type = FieldType.TEXT
    required = True


class RegistrationFactory(factory.Factory):
    class Meta:
        model = Registration

    status = RegistrationStatus.CONFIRMED
    answers = factory.LazyFunction(lambda: {"full_name": "Тест Тестов"})

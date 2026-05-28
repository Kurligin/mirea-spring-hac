"""CatalogFilter — value-object для фильтра каталога (3-символьный токен в callback-payload)."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.event import EventFormat, EventType


_CATEGORY_TO_CHAR: dict[EventType, str] = {
    EventType.OPEN_DAY: "o",
    EventType.MASTER_CLASS: "m",
    EventType.OLYMPIAD: "l",
    EventType.CONSULTATION: "c",
    EventType.OTHER: "e",
}
_CHAR_TO_CATEGORY: dict[str, EventType] = {v: k for k, v in _CATEGORY_TO_CHAR.items()}

_FORMAT_TO_CHAR: dict[EventFormat, str] = {
    EventFormat.OFFLINE: "f",
    EventFormat.ONLINE: "n",
    EventFormat.HYBRID: "h",
}
_CHAR_TO_FORMAT: dict[str, EventFormat] = {v: k for k, v in _FORMAT_TO_CHAR.items()}

_DATE_TO_CHAR = {"today": "t", "week": "w", "all": "-"}
_CHAR_TO_DATE = {v: k for k, v in _DATE_TO_CHAR.items()}


CATEGORY_LABELS: dict[EventType, str] = {
    EventType.OPEN_DAY: "День открытых дверей",
    EventType.MASTER_CLASS: "Мастер-класс",
    EventType.OLYMPIAD: "Олимпиада",
    EventType.CONSULTATION: "Консультация",
    EventType.OTHER: "Прочее",
}

FORMAT_LABELS_SHORT: dict[EventFormat, str] = {
    EventFormat.OFFLINE: "Очно",
    EventFormat.ONLINE: "Онлайн",
    EventFormat.HYBRID: "Гибрид",
}

DATE_LABELS: dict[str, str] = {
    "today": "Сегодня",
    "week": "На этой неделе",
    "all": "Все",
}


@dataclass(frozen=True)
class CatalogFilter:
    category: EventType | None = None
    date: str = "all"  # "today" | "week" | "all"
    format: EventFormat | None = None

    @property
    def is_default(self) -> bool:
        return self.category is None and self.date == "all" and self.format is None

    def encode(self) -> str:
        c = _CATEGORY_TO_CHAR.get(self.category, "-") if self.category else "-"
        d = _DATE_TO_CHAR.get(self.date, "-")
        f = _FORMAT_TO_CHAR.get(self.format, "-") if self.format else "-"
        return f"{c}{d}{f}"

    @classmethod
    def decode(cls, token: str) -> "CatalogFilter":
        """Битый/неполный токен → все измерения трактуются как «все»."""
        if not isinstance(token, str) or len(token) != 3:
            return cls()
        c_char, d_char, f_char = token[0], token[1], token[2]
        return cls(
            category=_CHAR_TO_CATEGORY.get(c_char),
            date=_CHAR_TO_DATE.get(d_char, "all"),
            format=_CHAR_TO_FORMAT.get(f_char),
        )

    def with_category(self, category: EventType | None) -> "CatalogFilter":
        return CatalogFilter(category=category, date=self.date, format=self.format)

    def with_date(self, date: str) -> "CatalogFilter":
        return CatalogFilter(category=self.category, date=date, format=self.format)

    def with_format(self, format: EventFormat | None) -> "CatalogFilter":
        return CatalogFilter(category=self.category, date=self.date, format=format)

    def summary_ru(self) -> str:
        """Человекочитаемая строка для шапки каталога: «Мастер-классы · На неделе»."""
        parts: list[str] = []
        if self.category is not None:
            parts.append(CATEGORY_LABELS[self.category])
        if self.date != "all":
            parts.append(DATE_LABELS[self.date])
        if self.format is not None:
            parts.append(FORMAT_LABELS_SHORT[self.format])
        return " · ".join(parts)


DEFAULT_TOKEN = "---"

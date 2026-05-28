"""Генерация deep-link URL для импорта события в календари (Google/Yandex/Outlook)
и .ics-ссылки для Apple/iOS.

URL-форматы:
- Google: https://calendar.google.com/calendar/render?action=TEMPLATE&...
- Yandex: https://calendar.yandex.ru/event?...
- Outlook web: https://outlook.live.com/calendar/0/deeplink/compose?...
- Apple: .ics-файл по нашему endpoint /api/calendar/<event_id>.ics
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode
from uuid import UUID

from app.core.config import get_settings
from app.models.event import Event


def _utc_compact(dt: datetime) -> str:
    """20260602T084500Z — Google/Outlook ждут UTC без разделителей."""
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _iso_local(dt: datetime) -> str:
    """ISO 8601 для Yandex."""
    return dt.astimezone(timezone.utc).isoformat()


def _event_window(event: Event) -> tuple[datetime, datetime]:
    start = event.starts_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = start + timedelta(minutes=event.duration_minutes)
    return start, end


def _details(event: Event) -> str:
    if event.description:
        return event.description.strip()
    return f"Запись через бота РТУ МИРЭА: «{event.title}»."


def google_url(event: Event) -> str:
    start, end = _event_window(event)
    params = {
        "action": "TEMPLATE",
        "text": event.title,
        "dates": f"{_utc_compact(start)}/{_utc_compact(end)}",
        "details": _details(event),
        "location": event.location or "",
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params, quote_via=quote)


def yandex_url(event: Event) -> str:
    start, end = _event_window(event)
    params = {
        "name": event.title,
        "description": _details(event),
        "location": event.location or "",
        "start": _iso_local(start),
        "end": _iso_local(end),
    }
    return "https://calendar.yandex.ru/event?" + urlencode(params, quote_via=quote)


def outlook_url(event: Event) -> str:
    start, end = _event_window(event)
    params = {
        "path": "/calendar/action/compose",
        "rru": "addevent",
        "subject": event.title,
        "body": _details(event),
        "location": event.location or "",
        "startdt": _iso_local(start),
        "enddt": _iso_local(end),
    }
    return "https://outlook.live.com/calendar/0/deeplink/compose?" + urlencode(params, quote_via=quote)


def apple_ics_url(event_id: UUID) -> str:
    """Apple/iOS подхватит .ics нативно."""
    base = get_settings().public_base_url.rstrip("/")
    return f"{base}/api/calendar/{event_id}.ics"


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def render_ics(event: Event) -> str:
    """RFC 5545 .ics для одного события."""
    start, end = _event_window(event)
    now = datetime.now(timezone.utc)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//RTU MIREA//Events Bot//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{event.id}@mirea-events",
        f"DTSTAMP:{_utc_compact(now)}",
        f"DTSTART:{_utc_compact(start)}",
        f"DTEND:{_utc_compact(end)}",
        f"SUMMARY:{_ics_escape(event.title)}",
        f"DESCRIPTION:{_ics_escape(_details(event))}",
    ]
    if event.location:
        lines.append(f"LOCATION:{_ics_escape(event.location)}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"

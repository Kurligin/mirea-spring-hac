"""Рендер QR-payload в PNG-байты."""
from __future__ import annotations

from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def render_qr_png(payload: str, *, box_size: int = 10, border: int = 4) -> bytes:
    """Сериализует строку payload в QR-PNG (bytes)."""
    img = qrcode.make(
        payload,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

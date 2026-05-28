import re
import secrets

ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # без I, O для устранения визуальной неоднозначности
DIGITS = "0123456789"
PATTERN = re.compile(r"^[A-HJ-NP-Z]{3}-\d{4}$")


def generate_short_code() -> str:
    """Генерирует короткий код вида XXX-1234.

    Алфавит исключает I и O чтобы избежать путаницы с 1 и 0.
    Использует secrets для криптографически стойкой случайности.
    """
    letters = "".join(secrets.choice(ALPHA) for _ in range(3))
    digits = "".join(secrets.choice(DIGITS) for _ in range(4))
    return f"{letters}-{digits}"


def validate_short_code(code: str) -> bool:
    """Проверяет формат кода: XXX-1234 (без I/O)."""
    return bool(PATTERN.fullmatch(code))

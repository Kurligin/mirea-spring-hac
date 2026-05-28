import re

from app.services.short_code import generate_short_code, validate_short_code


def test_generated_matches_format():
    code = generate_short_code()
    assert re.fullmatch(r"[A-HJ-NP-Z]{3}-\d{4}", code), code


def test_unique_within_batch():
    codes = {generate_short_code() for _ in range(100)}
    assert len(codes) >= 95  # Slight collision tolerance


def test_validate_correct():
    assert validate_short_code("ABC-1234") is True
    assert validate_short_code("ZZZ-9999") is True


def test_validate_incorrect():
    assert validate_short_code("abc-1234") is False
    assert validate_short_code("IOO-1234") is False  # I, O запрещены
    assert validate_short_code("ABC-12") is False
    assert validate_short_code("ABC1234") is False
    assert validate_short_code("") is False
    assert validate_short_code("ABCD-1234") is False

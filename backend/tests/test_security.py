import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_then_verify_ok():
    h = hash_password("secret123")
    assert verify_password("secret123", h) is True
    assert verify_password("wrong", h) is False


def test_jwt_roundtrip():
    token = create_access_token(subject="admin-id-uuid", extra={"role": "super"})
    payload = decode_access_token(token)
    assert payload["sub"] == "admin-id-uuid"
    assert payload["role"] == "super"


def test_jwt_tampered_token_raises():
    token = create_access_token(subject="x")
    bad = token + "x"
    with pytest.raises(Exception):
        decode_access_token(bad)

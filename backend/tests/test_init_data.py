import hashlib
import hmac
import json
import time
from urllib.parse import quote

import pytest

from app.core.init_data import InitDataValidator, InvalidInitData


def _make_init_data(bot_token: str, payload: dict, auth_date: int | None = None) -> str:
    if auth_date is None:
        auth_date = int(time.time())
    data = dict(payload)
    data["auth_date"] = auth_date
    # canonical: key=value\n...
    items = []
    for k in sorted(data.keys()):
        v = data[k]
        if isinstance(v, (dict, list)):
            v = json.dumps(v, separators=(",", ":"), ensure_ascii=False)
        items.append(f"{k}={v}")
    payload_str = "\n".join(items)
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    sig = hmac.new(secret, payload_str.encode(), hashlib.sha256).hexdigest()
    # url-encoded querystring with hash
    parts = []
    for k in sorted(data.keys()):
        v = data[k]
        if isinstance(v, (dict, list)):
            v = json.dumps(v, separators=(",", ":"), ensure_ascii=False)
        parts.append(f"{k}={quote(str(v), safe='')}")
    parts.append(f"hash={sig}")
    return "&".join(parts)


def test_valid_init_data_passes():
    payload = {"user": {"id": 42, "first_name": "Иван"}, "chat": {"id": 100, "type": "private"}}
    init = _make_init_data("bot-token-123", payload)
    v = InitDataValidator(bot_token="bot-token-123", max_age_seconds=86400)
    parsed = v.validate(init)
    assert parsed["user"]["id"] == 42


def test_tampered_hash_rejected():
    init = _make_init_data("bot-token-123", {"user": {"id": 1}})
    bad = init[:-1] + ("0" if init[-1] != "0" else "1")
    v = InitDataValidator(bot_token="bot-token-123", max_age_seconds=86400)
    with pytest.raises(InvalidInitData):
        v.validate(bad)


def test_wrong_token_rejected():
    init = _make_init_data("token-A", {"user": {"id": 1}})
    v = InitDataValidator(bot_token="token-B", max_age_seconds=86400)
    with pytest.raises(InvalidInitData):
        v.validate(init)


def test_expired_init_data_rejected():
    old_ts = int(time.time()) - 100000
    init = _make_init_data("bot-token-123", {"user": {"id": 1}}, auth_date=old_ts)
    v = InitDataValidator(bot_token="bot-token-123", max_age_seconds=86400)
    with pytest.raises(InvalidInitData):
        v.validate(init)


def test_missing_hash_rejected():
    v = InitDataValidator(bot_token="bot-token-123", max_age_seconds=86400)
    with pytest.raises(InvalidInitData):
        v.validate("user=foo&auth_date=123")

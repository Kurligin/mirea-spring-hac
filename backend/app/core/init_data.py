import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import unquote


class InvalidInitData(Exception):
    pass


class InitDataValidator:
    """Валидация launch params от MAX mini-app.

    Telegram-style двухстадийная подпись:
        secret = HMAC-SHA256(b"WebAppData", bot_token)
        sig    = HMAC-SHA256(secret, sorted "key=value\\n..." payload)
    """

    def __init__(self, *, bot_token: str, max_age_seconds: int = 86400):
        self.bot_token = bot_token.encode()
        self.max_age = max_age_seconds

    def validate(self, init_data: str) -> dict[str, Any]:
        pairs = [p for p in init_data.split("&") if p]
        if not pairs:
            raise InvalidInitData("empty init data")

        parsed: dict[str, str] = {}
        for p in pairs:
            if "=" not in p:
                raise InvalidInitData(f"malformed pair: {p}")
            k, v = p.split("=", 1)
            parsed[k] = unquote(v)

        received_hash = parsed.pop("hash", None)
        if not received_hash:
            raise InvalidInitData("missing hash")

        items = [f"{k}={parsed[k]}" for k in sorted(parsed.keys())]
        payload_str = "\n".join(items)

        secret_key = hmac.new(b"WebAppData", self.bot_token, hashlib.sha256).digest()
        computed = hmac.new(secret_key, payload_str.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(computed, received_hash):
            raise InvalidInitData("hash mismatch")

        auth_date_str = parsed.get("auth_date")
        if not auth_date_str:
            raise InvalidInitData("missing auth_date")
        try:
            auth_date = int(auth_date_str)
        except ValueError as e:
            raise InvalidInitData("invalid auth_date") from e
        if time.time() - auth_date > self.max_age:
            raise InvalidInitData("init data expired")

        result: dict[str, Any] = {}
        for k, v in parsed.items():
            if k in ("user", "chat") or (v.startswith("{") and v.endswith("}")):
                try:
                    result[k] = json.loads(v)
                    continue
                except json.JSONDecodeError:
                    pass
            result[k] = v
        result["auth_date"] = auth_date
        return result

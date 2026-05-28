import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from uuid import UUID


class QRDecodeError(Exception):
    pass


class QRSignatureError(Exception):
    pass


class QRExpired(Exception):
    pass


@dataclass(frozen=True)
class QRPayload:
    event_id: UUID
    reg_id: UUID
    user_id: UUID
    bucket: int
    iat: int


class QRService:
    """Ротирующийся QR-payload в стиле TOTP.

    bucket = floor(now / bucket_seconds)
    payload = base64({event_id, reg_id, user_id, bucket, iat, sig})
    sig = HMAC-SHA256(secret, "event_id:reg_id:user_id:bucket")

    При верификации принимаем текущий bucket или bucket-1 (fuzz_window=1)
    → фактическое окно жизни одного QR ~15-30 сек.
    """

    def __init__(self, *, secret: str, bucket_seconds: int = 15, fuzz_window: int = 1):
        if len(secret) < 16:
            raise ValueError("secret too short")
        self.secret = secret.encode()
        self.bucket_seconds = bucket_seconds
        self.fuzz_window = fuzz_window

    def _bucket(self, now: float) -> int:
        return int(now) // self.bucket_seconds

    def _sign(self, event_id: UUID, reg_id: UUID, user_id: UUID, bucket: int) -> str:
        msg = f"{event_id}:{reg_id}:{user_id}:{bucket}".encode()
        return hmac.new(self.secret, msg, hashlib.sha256).hexdigest()

    def generate(
        self,
        *,
        event_id: UUID,
        reg_id: UUID,
        user_id: UUID,
        now: float | None = None,
    ) -> str:
        ts = now if now is not None else time.time()
        bucket = self._bucket(ts)
        sig = self._sign(event_id, reg_id, user_id, bucket)
        body = {
            "event_id": str(event_id),
            "reg_id": str(reg_id),
            "user_id": str(user_id),
            "bucket": bucket,
            "iat": int(ts),
            "sig": sig,
        }
        raw = json.dumps(body, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode()

    def verify(self, payload_b64: str, *, now: float | None = None) -> QRPayload:
        try:
            raw = base64.urlsafe_b64decode(payload_b64.encode())
            body = json.loads(raw.decode())
        except Exception as e:
            raise QRDecodeError(str(e)) from e

        try:
            event_id = UUID(body["event_id"])
            reg_id = UUID(body["reg_id"])
            user_id = UUID(body["user_id"])
            bucket = int(body["bucket"])
            iat = int(body["iat"])
            sig = body["sig"]
        except (KeyError, ValueError, TypeError) as e:
            raise QRDecodeError(f"malformed payload: {e}") from e

        expected = self._sign(event_id, reg_id, user_id, bucket)
        if not hmac.compare_digest(expected, sig):
            raise QRSignatureError("signature mismatch")

        ts = now if now is not None else time.time()
        current = self._bucket(ts)
        if abs(current - bucket) > self.fuzz_window:
            raise QRExpired(f"bucket diff {abs(current - bucket)} > fuzz {self.fuzz_window}")

        return QRPayload(event_id=event_id, reg_id=reg_id, user_id=user_id, bucket=bucket, iat=iat)

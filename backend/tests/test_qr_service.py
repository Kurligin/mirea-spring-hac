import base64
import json
import time
from uuid import uuid4

import pytest

from app.core.qr import QRService, QRDecodeError, QRExpired, QRSignatureError


def test_generate_then_verify_ok():
    svc = QRService(secret="qr-secret-32bytes-minimum-please", bucket_seconds=15, fuzz_window=1)
    event_id = uuid4()
    reg_id = uuid4()
    user_id = uuid4()
    payload = svc.generate(event_id=event_id, reg_id=reg_id, user_id=user_id)
    parsed = svc.verify(payload)
    assert parsed.event_id == event_id
    assert parsed.reg_id == reg_id
    assert parsed.user_id == user_id


def test_tampered_signature_rejected():
    svc = QRService(secret="s" * 32, bucket_seconds=15, fuzz_window=1)
    payload = svc.generate(event_id=uuid4(), reg_id=uuid4(), user_id=uuid4())
    decoded = json.loads(base64.urlsafe_b64decode(payload).decode())
    decoded["reg_id"] = str(uuid4())  # переписали reg_id, но sig прежний
    bad = base64.urlsafe_b64encode(json.dumps(decoded).encode()).decode()
    with pytest.raises(QRSignatureError):
        svc.verify(bad)


def test_wrong_secret_rejected():
    a = QRService(secret="a" * 32, bucket_seconds=15, fuzz_window=1)
    b = QRService(secret="b" * 32, bucket_seconds=15, fuzz_window=1)
    payload = a.generate(event_id=uuid4(), reg_id=uuid4(), user_id=uuid4())
    with pytest.raises(QRSignatureError):
        b.verify(payload)


def test_old_bucket_rejected():
    svc = QRService(secret="s" * 32, bucket_seconds=15, fuzz_window=1)
    event_id = uuid4(); reg_id = uuid4(); user_id = uuid4()
    payload = svc.generate(
        event_id=event_id, reg_id=reg_id, user_id=user_id,
        now=time.time() - 60,  # 4 bucket'а назад
    )
    with pytest.raises(QRExpired):
        svc.verify(payload, now=time.time())


def test_fuzz_window_accepts_previous_bucket():
    svc = QRService(secret="s" * 32, bucket_seconds=15, fuzz_window=1)
    event_id = uuid4(); reg_id = uuid4(); user_id = uuid4()
    t0 = time.time()
    # payload в bucket = floor(t0/15)
    payload = svc.generate(event_id=event_id, reg_id=reg_id, user_id=user_id, now=t0)
    # верифицируем "одним bucket позже" — должно работать
    parsed = svc.verify(payload, now=t0 + 14)
    assert parsed.event_id == event_id


def test_malformed_payload_rejected():
    svc = QRService(secret="s" * 32, bucket_seconds=15, fuzz_window=1)
    with pytest.raises(QRDecodeError):
        svc.verify("!!!not-base64!!!")

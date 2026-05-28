import asyncio
import time

import pytest

from app.core.rate_limiter import TokenBucket


async def test_within_capacity_passes_immediately():
    bucket = TokenBucket(rate=30, capacity=30)
    start = time.monotonic()
    for _ in range(10):
        await bucket.acquire()
    assert time.monotonic() - start < 0.1


async def test_over_capacity_blocks_until_refill():
    bucket = TokenBucket(rate=30, capacity=5)
    for _ in range(5):
        await bucket.acquire()
    start = time.monotonic()
    await bucket.acquire()
    elapsed = time.monotonic() - start
    # 1 token at rate=30/s = ~33ms wait
    assert 0.02 < elapsed < 0.2


async def test_acquire_n_tokens():
    bucket = TokenBucket(rate=30, capacity=10)
    await bucket.acquire(n=10)
    start = time.monotonic()
    await bucket.acquire(n=3)
    elapsed = time.monotonic() - start
    # 3 tokens at 30/s = 100ms
    assert 0.08 < elapsed < 0.25

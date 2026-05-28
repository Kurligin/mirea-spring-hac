import asyncio
import time


class TokenBucket:
    """Async token-bucket rate limiter.

    Thread-safe under single asyncio event loop only.
    """

    def __init__(self, rate: float, capacity: int):
        if rate <= 0 or capacity <= 0:
            raise ValueError("rate and capacity must be > 0")
        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    async def acquire(self, n: int = 1) -> None:
        if n > self.capacity:
            raise ValueError(f"requested {n} tokens but capacity is {self.capacity}")
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= n:
                    self._tokens -= n
                    return
                deficit = n - self._tokens
                wait = deficit / self.rate
                await asyncio.sleep(wait)

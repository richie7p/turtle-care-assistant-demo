import asyncio
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import HTTPException, status

from ..config import Settings


class AIRateLimiter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._active: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
        self._global = asyncio.Semaphore(settings.ai_global_concurrency)

    @asynccontextmanager
    async def limit(self, user_id: str):
        now = time.monotonic()
        async with self._lock:
            recent = self._requests[user_id]
            while recent and now - recent[0] >= 60:
                recent.popleft()
            if len(recent) >= self.settings.ai_requests_per_minute:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="提問速度太快，請稍候一分鐘。")
            if self._active[user_id] >= self.settings.ai_per_user_concurrency:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="上一個 AI 回應仍在進行中。")
            recent.append(now)
            self._active[user_id] += 1
        await self._global.acquire()
        try:
            yield
        finally:
            self._global.release()
            async with self._lock:
                self._active[user_id] = max(0, self._active[user_id] - 1)


_limiter: AIRateLimiter | None = None


def get_ai_limiter(settings: Settings) -> AIRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = AIRateLimiter(settings)
    return _limiter


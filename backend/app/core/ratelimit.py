import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from ..config import get_settings

_hits = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    if get_settings().trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def reset():
    with _lock:
        _hits.clear()


def rate_limit(bucket: str, limit: int, window: int):
    def dependency(request: Request):
        if not get_settings().rate_limit_enabled:
            return
        key = f"{bucket}:{client_ip(request)}"
        now = time.monotonic()
        with _lock:
            queue = _hits[key]
            while queue and now - queue[0] > window:
                queue.popleft()
            if len(queue) >= limit:
                raise HTTPException(429, "Too many requests. Please wait a moment and try again.",
                                    headers={"Retry-After": str(window)})
            queue.append(now)
    return dependency

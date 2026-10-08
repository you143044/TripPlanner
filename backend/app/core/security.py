"""安全工具: IP获取、滑动窗口限流器、请求体大小限制中间件"""

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict, Optional

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import get_settings

# 客户端真实IP: 优先取反向代理头,回退到直连地址
def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


class SlidingWindowRateLimiter:
    """内存滑动窗口限流器(单进程适用;多worker需外置Redis)"""

    def __init__(self):
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        """key在window内调用不超过limit则放行"""
        now = time.time()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self, key: str):
        with self._lock:
            self._hits.pop(key, None)


# 全局限流器实例
_limiter = SlidingWindowRateLimiter()


def rate_limit_dependency(
    limit: int,
    window_seconds: int,
    scope: str,
):
    """生成一个FastAPI依赖: 按 IP(+可选user) 限流,超限抛429"""
    settings = get_settings()

    def _dep(request: Request):
        if not settings.enable_rate_limit:
            return
        ip = get_client_ip(request)
        user = request.headers.get("x-user-id", "").strip()
        key_user = f"{scope}:{ip}:{user[:64]}" if user else f"{scope}:{ip}"
        if not _limiter.allow(key_user, limit, window_seconds):
            retry = _limiter  # noqa
            raise HTTPException(
                status_code=429,
                detail="请求过于频繁,请稍后再试",
            )
    return _dep


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """限制请求体大小,超限返回413(防超大payload)"""

    def __init__(self, app, max_size: int = 64 * 1024):
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        length = request.headers.get("content-length")
        if length:
            try:
                if int(length) > self.max_size:
                    from starlette.responses import JSONResponse
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "请求体过大"},
                    )
            except ValueError:
                pass
        response = await call_next(request)
        return response
"""请求日志中间件。

记录所有 API 请求的 method、path、status_code 和处理耗时。
成功和异常路径均有记录。
"""

import time

from loguru import logger
from starlette.requests import Request


async def request_logging_middleware(request: Request, call_next):
    """记录所有 API 请求的 method/path/status/duration_ms。

    成功路径：logger.bind(event="request_complete").info(...)
    异常路径：logger.bind(event="request_failed").error(...)
    """
    start = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.bind(event="request_complete").info(
            "{method} {path} → {status} ({duration:.1f}ms)",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration=round(duration_ms, 1),
        )
        return response
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.bind(event="request_failed").error(
            "{method} {path} → ERROR: {error} ({duration:.1f}ms)",
            method=request.method,
            path=request.url.path,
            error=str(e),
            duration=round(duration_ms, 1),
        )
        raise

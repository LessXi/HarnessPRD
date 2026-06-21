"""Correlation ID 中间件。

从 X-Correlation-ID 请求头提取或生成 corr_id，
用 logger.contextualize 包裹整个请求处理链使其在日志中可见。
"""

from uuid import uuid4

from loguru import logger
from starlette.requests import Request


async def correlation_middleware(request: Request, call_next):
    """从 X-Correlation-ID 请求头提取或生成 corr_id，注入日志上下文。

    1. 提取或生成 corr_id
    2. 存入 request.state.correlation_id
    3. 用 logger.contextualize 注入日志上下文
    4. 在响应头中设置 X-Correlation-ID
    """
    corr_id = request.headers.get("X-Correlation-ID", str(uuid4()))
    with logger.contextualize(corr_id=corr_id):
        try:
            request.state.correlation_id = corr_id
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = corr_id
            return response
        finally:
            pass  # contextualize 自动退出

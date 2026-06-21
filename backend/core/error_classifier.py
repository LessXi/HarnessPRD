"""错误分类器 —— 根据异常类型和消息内容返回结构化分类。"""

import enum
from typing import Any

import httpx


class ErrorCategory(str, enum.Enum):
    """错误分类枚举"""

    LLM_RATE_LIMIT = "llm_rate_limit"
    LLM_TIMEOUT = "llm_timeout"
    LLM_CONTENT_FILTER = "llm_content_filter"
    LLM_AUTH = "llm_auth"
    LLM_UNKNOWN = "llm_unknown"
    HTTP_CLIENT_ERROR = "http_client_error"
    HTTP_SERVER_ERROR = "http_server_error"
    BUSINESS = "business"
    UNKNOWN = "unknown"


def classify_error(exception: Exception) -> ErrorCategory:
    """根据异常类型和消息内容返回 ErrorCategory。

    匹配顺序：
    1. 异常类名
    2. 异常消息关键词
    3. httpx.HTTPStatusError 状态码
    4. 兜底 UNKNOWN
    """
    class_name = type(exception).__name__
    message = str(exception).lower()

    # === 第一关：类名匹配 ===
    if class_name == "RateLimitError":
        return ErrorCategory.LLM_RATE_LIMIT
    if class_name == "APITimeoutError" or class_name == "Timeout":
        return ErrorCategory.LLM_TIMEOUT
    if class_name == "ContentFilterError":
        return ErrorCategory.LLM_CONTENT_FILTER
    if class_name == "AuthenticationError":
        return ErrorCategory.LLM_AUTH

    # === 第二关：异常消息关键词匹配 ===
    # 注意：先做普通消息匹配，让消息关键词优先于 httpx 状态码
    if _message_indicates_rate_limit(message):
        return ErrorCategory.LLM_RATE_LIMIT
    if _message_indicates_timeout(message):
        return ErrorCategory.LLM_TIMEOUT
    if _message_indicates_content_filter(message):
        return ErrorCategory.LLM_CONTENT_FILTER
    if _message_indicates_auth(message):
        return ErrorCategory.LLM_AUTH

    # === 第三关：httpx HTTPStatusError ===
    if isinstance(exception, httpx.HTTPStatusError):
        status_code = exception.response.status_code
        if 400 <= status_code < 500:
            return ErrorCategory.HTTP_CLIENT_ERROR
        if 500 <= status_code < 600:
            return ErrorCategory.HTTP_SERVER_ERROR

    return ErrorCategory.UNKNOWN


def _message_indicates_rate_limit(message: str) -> bool:
    return "rate" in message or "429" in message


def _message_indicates_timeout(message: str) -> bool:
    return "timeout" in message or "timed out" in message


def _message_indicates_content_filter(message: str) -> bool:
    return "content" in message and "filter" in message


def _message_indicates_auth(message: str) -> bool:
    keywords = ("auth", "401", "403", "key")
    return any(kw in message for kw in keywords)

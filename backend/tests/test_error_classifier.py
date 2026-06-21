"""测试 error_classifier 模块"""

import httpx
import pytest

from core.error_classifier import ErrorCategory, classify_error


class RateLimitError(Exception):
    """模仿 LangChain/OpenAI 的 RateLimitError"""
    pass


class APITimeoutError(Exception):
    """模仿 LangChain/OpenAI 的 APITimeoutError"""
    pass


class ContentFilterError(Exception):
    """模仿 LangChain/OpenAI 的 ContentFilterError"""
    pass


class AuthenticationError(Exception):
    """模仿 LangChain/OpenAI 的 AuthenticationError"""
    pass


def mock_response(status_code: int) -> httpx.Response:
    """创建 mock httpx.Response"""
    return httpx.Response(status_code=status_code, request=httpx.Request("GET", "http://example.com"))


# === 类名匹配 ===

def test_classify_by_class_name_rate_limit():
    """类名 RateLimitError → LLM_RATE_LIMIT"""
    exc = RateLimitError("rate limit exceeded")
    assert classify_error(exc) == ErrorCategory.LLM_RATE_LIMIT


def test_classify_by_class_name_timeout():
    """类名 APITimeoutError → LLM_TIMEOUT"""
    exc = APITimeoutError("request timed out")
    assert classify_error(exc) == ErrorCategory.LLM_TIMEOUT


def test_classify_by_class_name_content_filter():
    """类名 ContentFilterError → LLM_CONTENT_FILTER"""
    exc = ContentFilterError("content filter triggered")
    assert classify_error(exc) == ErrorCategory.LLM_CONTENT_FILTER


def test_classify_by_class_name_auth():
    """类名 AuthenticationError → LLM_AUTH"""
    exc = AuthenticationError("invalid API key")
    assert classify_error(exc) == ErrorCategory.LLM_AUTH


# === 异常消息匹配 ===

def test_classify_by_message_rate():
    """消息含 'rate' → LLM_RATE_LIMIT"""
    exc = Exception("rate limit exceeded, retry later")
    assert classify_error(exc) == ErrorCategory.LLM_RATE_LIMIT


def test_classify_by_message_429():
    """消息含 '429' → LLM_RATE_LIMIT"""
    exc = Exception("429 Too Many Requests")
    assert classify_error(exc) == ErrorCategory.LLM_RATE_LIMIT


def test_classify_by_message_timeout():
    """消息含 'timeout' → LLM_TIMEOUT"""
    exc = Exception("request timed out after 30s")
    assert classify_error(exc) == ErrorCategory.LLM_TIMEOUT


def test_classify_by_message_timed_out():
    """消息含 'timed out' → LLM_TIMEOUT"""
    exc = Exception("connection timed out")
    assert classify_error(exc) == ErrorCategory.LLM_TIMEOUT


def test_classify_by_message_content_filter():
    """消息同时含 'content' 和 'filter' → LLM_CONTENT_FILTER"""
    exc = Exception("content filter triggered: inappropriate content")
    assert classify_error(exc) == ErrorCategory.LLM_CONTENT_FILTER


def test_classify_by_message_auth():
    """消息含 'auth' → LLM_AUTH"""
    exc = Exception("authentication failed")
    assert classify_error(exc) == ErrorCategory.LLM_AUTH


def test_classify_by_message_401():
    """消息含 '401' → LLM_AUTH"""
    exc = Exception("401 Unauthorized")
    assert classify_error(exc) == ErrorCategory.LLM_AUTH


def test_classify_by_message_403():
    """消息含 '403' → LLM_AUTH"""
    exc = Exception("403 Forbidden")
    assert classify_error(exc) == ErrorCategory.LLM_AUTH


def test_classify_by_message_key():
    """消息含 'key' → LLM_AUTH"""
    exc = Exception("invalid API key provided")
    assert classify_error(exc) == ErrorCategory.LLM_AUTH


# === HTTP client 4xx ===

def test_classify_http_4xx():
    """HTTPStatusError 4xx → HTTP_CLIENT_ERROR"""
    exc = httpx.HTTPStatusError("Client error", request=mock_response(404).request, response=mock_response(404))
    assert classify_error(exc) == ErrorCategory.HTTP_CLIENT_ERROR


# === HTTP server 5xx ===

def test_classify_http_5xx():
    """HTTPStatusError 5xx → HTTP_SERVER_ERROR"""
    exc = httpx.HTTPStatusError("Server error", request=mock_response(500).request, response=mock_response(500))
    assert classify_error(exc) == ErrorCategory.HTTP_SERVER_ERROR


# === 消息匹配优先级高于 httpx 状态码 (rate 429) ===

def test_httpx_429_matches_rate_limit():
    """HTTPStatusError 4xx 但消息含 'rate' → LLM_RATE_LIMIT (消息优先)"""
    exc = httpx.HTTPStatusError("rate limit: 429", request=mock_response(429).request, response=mock_response(429))
    assert classify_error(exc) == ErrorCategory.LLM_RATE_LIMIT


# === 未知异常 ===

def test_classify_unknown():
    """不匹配任何模式 → UNKNOWN"""
    exc = Exception("some random error with no known pattern")
    assert classify_error(exc) == ErrorCategory.UNKNOWN


# === 空消息 ===

def test_classify_empty_message():
    """空消息 → UNKNOWN"""
    exc = Exception("")
    assert classify_error(exc) == ErrorCategory.UNKNOWN

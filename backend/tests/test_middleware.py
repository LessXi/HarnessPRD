"""测试 CorrelationMiddleware 和 RequestLoggingMiddleware。

测试策略：
- 用 Starlette 创建小型测试 app，手工注册 middleware
- TestClient 发送请求验证行为
- 用 loguru 内存 sink 捕获日志输出验证日志记录
"""
import pytest
from loguru import logger as loguru_logger
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient


# ── helpers ──────────────────────────────────────────────────────────

def _make_health_app():
    """创建一个返回 {"status":"ok"} 的小型测试 app。"""
    async def health(request):
        return JSONResponse({"status": "ok"})

    async def error(request):
        raise ValueError("simulated error")

    app = Starlette(
        routes=[
            Route("/health", endpoint=health),
            Route("/error", endpoint=error),
        ],
    )
    return app


# ── CorrelationMiddleware ────────────────────────────────────────────

class TestCorrelationMiddleware:
    """验证 correlation_middleware 行为"""

    def test_sets_correlation_id_header(self):
        """请求后响应头应包含 X-Correlation-ID"""
        from middleware.correlation import correlation_middleware

        app = _make_health_app()
        app.add_middleware(BaseHTTPMiddleware, dispatch=correlation_middleware)  # type: ignore[arg-type]

        client = TestClient(app)
        resp = client.get("/health")

        assert resp.status_code == 200
        assert "X-Correlation-ID" in resp.headers
        # 确保生成的值是合法的 UUID 格式
        assert len(resp.headers["X-Correlation-ID"]) > 0

    def test_reuses_incoming_correlation_id(self):
        """请求携带 X-Correlation-ID 时，响应头应使用同一值"""
        from middleware.correlation import correlation_middleware

        app = _make_health_app()
        app.add_middleware(BaseHTTPMiddleware, dispatch=correlation_middleware)  # type: ignore[arg-type]

        client = TestClient(app)
        custom_id = "my-test-corr-id-001"
        resp = client.get("/health", headers={"X-Correlation-ID": custom_id})

        assert resp.status_code == 200
        assert resp.headers["X-Correlation-ID"] == custom_id

    def test_correlation_id_is_unique_per_request(self):
        """连续请求应获得不同的 corr_id（未传入请求头时）"""
        from middleware.correlation import correlation_middleware

        app = _make_health_app()
        app.add_middleware(BaseHTTPMiddleware, dispatch=correlation_middleware)  # type: ignore[arg-type]

        client = TestClient(app)
        resp1 = client.get("/health")
        resp2 = client.get("/health")

        id1 = resp1.headers["X-Correlation-ID"]
        id2 = resp2.headers["X-Correlation-ID"]
        assert id1 != id2, "连续请求应获得不同的 corr_id"


# ── RequestLoggingMiddleware ─────────────────────────────────────────

class TestRequestLoggingMiddleware:
    """验证 request_logging_middleware 记录日志的行为"""

    @pytest.fixture(autouse=True)
    def _capture_logs(self):
        """每个测试前配置内存 sink 捕获日志"""
        loguru_logger.remove()  # 移除默认 sink
        self.captured: list[str] = []
        handler_id = loguru_logger.add(
            lambda msg: self.captured.append(str(msg)),
            format="{message}",
            level="DEBUG",
            serialize=False,
        )
        yield
        loguru_logger.remove(handler_id)
        # 恢复：添加一个空 sink 防止测试间干扰
        loguru_logger.add(lambda _: None, level="DEBUG")

    def _assert_log_contains(self, *keywords: str) -> None:
        """断言捕获日志中包含同时包含所有关键字的条目"""
        for entry in self.captured:
            if all(kw in entry for kw in keywords):
                return
        pytest.fail(
            f"未找到同时包含 {keywords} 的日志条目。"
            f"\n  捕获日志 ({len(self.captured)} 条): {self.captured}"
        )

    def test_logs_successful_request(self):
        """成功请求应记录 method/path/status/duration_ms"""
        from middleware.request_logging import request_logging_middleware

        app = _make_health_app()
        app.add_middleware(BaseHTTPMiddleware, dispatch=request_logging_middleware)  # type: ignore[arg-type]

        client = TestClient(app)
        resp = client.get("/health")

        assert resp.status_code == 200
        self._assert_log_contains("GET", "/health", "200")

    def test_logs_failed_request(self):
        """500 错误的请求应记录 ERROR 和异常信息"""
        from middleware.request_logging import request_logging_middleware

        app = _make_health_app()
        app.add_middleware(BaseHTTPMiddleware, dispatch=request_logging_middleware)  # type: ignore[arg-type]

        client = TestClient(app)
        with pytest.raises(ValueError, match="simulated error"):
            client.get("/error")

        # 即使异常被抛出，日志仍应被记录
        self._assert_log_contains("GET", "/error", "ERROR", "simulated error")

    def test_log_includes_duration(self):
        """日志条目应包含 duration_ms 或 'ms' 字样"""
        from middleware.request_logging import request_logging_middleware

        app = _make_health_app()
        app.add_middleware(BaseHTTPMiddleware, dispatch=request_logging_middleware)  # type: ignore[arg-type]

        client = TestClient(app)
        resp = client.get("/health")

        assert resp.status_code == 200
        self._assert_log_contains("GET", "/health", "ms")

"""测试 core.config 的可观测性字段验证。"""

import logging
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from core.config import Settings


class TestLogLevel:
    """LOG_LEVEL 字段校验测试"""

    def test_log_level_valid(self):
        """验证合法值：INFO→INFO, debug→DEBUG"""
        s1 = Settings(log_level="INFO")
        assert s1.log_level == "INFO"

        s2 = Settings(log_level="debug")
        assert s2.log_level == "DEBUG"

        s3 = Settings(log_level="Warning")
        assert s3.log_level == "WARNING"

        s4 = Settings(log_level="error")
        assert s4.log_level == "ERROR"

    def test_log_level_invalid(self):
        """验证非法值抛 ValueError"""
        with pytest.raises(ValueError, match="LOG_LEVEL"):
            Settings(log_level="INVALID")

        with pytest.raises(ValueError, match="LOG_LEVEL"):
            Settings(log_level="verbose")

        with pytest.raises(ValueError, match="LOG_LEVEL"):
            Settings(log_level="")


class TestLangSmithTracing:
    """LangSmith 追踪配置校验测试"""

    def test_tracing_without_key_warning(self, caplog):
        """tracing=true + api_key="" → 输出 warning"""
        caplog.set_level(logging.WARNING)
        Settings(
            langchain_tracing_v2=True,
            langchain_api_key="",
        )
        assert any(
            "LANGCHAIN_TRACING_V2=true but LANGCHAIN_API_KEY is not set"
            in record.message
            for record in caplog.records
        ), "应输出缺少 API key 的 warning"

    def test_tracing_with_key(self, caplog):
        """tracing=true + api_key="sk-xxx" → 无 warning"""
        caplog.set_level(logging.WARNING)
        Settings(
            langchain_tracing_v2=True,
            langchain_api_key="sk-xxx",
        )
        # 检查是否有 tracing 相关的 warning
        tracing_warnings = [
            record
            for record in caplog.records
            if "LANGCHAIN_TRACING" in record.message
        ]
        assert len(tracing_warnings) == 0, "不应输出 tracing 相关 warning"

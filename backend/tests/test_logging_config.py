"""测试 loguru 日志配置模块。

测试策略：
- setup_logging: 验证 sink 数量增加
- InterceptHandler: 验证标准 logging 记录转发到 loguru
- get_logger: 验证返回的 logger 带有正确的 extra 绑定
"""

import logging

import pytest
from loguru import logger as loguru_logger

from core.logging_config import InterceptHandler, get_logger, setup_logging


def test_setup_logging_adds_sinks():
    """setup_logging() 应添加 console 和 file 两个 sink。"""
    # 确保从干净状态开始
    loguru_logger.remove()

    initial_count = len(loguru_logger._core.handlers)
    setup_logging()
    after_count = len(loguru_logger._core.handlers)

    # 至少增加了 2 个 handler（console + ndjson file）
    assert after_count >= initial_count + 2

    # 清理
    loguru_logger.remove()


def test_intercept_handler_logs():
    """InterceptHandler 应将标准 logging 记录转发到 loguru。"""
    loguru_logger.remove()
    setup_logging()

    # 内存 sink 捕获 loguru 输出
    captured: list[str] = []
    handler_id = loguru_logger.add(
        lambda msg: captured.append(str(msg)),
        format="{message}",
        level="DEBUG",
    )

    # 创建标准 logger 并附加 InterceptHandler
    std_logger = logging.getLogger("test_intercept_handler")
    std_logger.handlers.clear()
    std_logger.setLevel(logging.DEBUG)
    std_logger.addHandler(InterceptHandler())
    std_logger.propagate = False

    test_msg = "hello_from_standard_logging"
    std_logger.info(test_msg)

    loguru_logger.remove(handler_id)

    assert any(
        test_msg in entry for entry in captured
    ), f"预期 '{test_msg}' 出现在 loguru 捕获输出中，实际: {captured}"

    loguru_logger.remove()


def test_get_logger_binds_module():
    """get_logger() 应返回绑定了 module 的 logger。

    验证方式：通过内存 sink 捕获输出，检查日志中包含 module 名称。
    """
    loguru_logger.remove()

    logger_instance = get_logger("test_module")

    # 类型检查：确保返回的是 loguru logger（type(logger) 即 Logger 类）
    assert type(logger_instance).__name__ == "Logger", (
        f"期望返回 loguru Logger，实际类型: {type(logger_instance).__name__}"
    )

    # 功能验证：通过 sink 捕获实际输出，检查 module extra 生效
    captured: list[str] = []
    handler_id = loguru_logger.add(
        lambda msg: captured.append(str(msg)),
        format="{extra[module]}",
        level="DEBUG",
    )

    logger_instance.info("dummy")
    loguru_logger.remove(handler_id)

    assert any("test_module" in entry for entry in captured), (
        f"预期捕获输出包含 'test_module'，实际: {captured}"
    )

"""Loguru 日志配置：双 sink + InterceptHandler + get_logger 工厂。

用法：
    from core.logging_config import setup_logging, get_logger, InterceptHandler

    # 应用启动时调用一次
    setup_logging()

    # 模块级 logger
    logger = get_logger(__name__)
    logger.info("hello")

    # 如需将标准 logging 库接入 loguru（例如 uvicorn 的日志）
    import logging
    logging.getLogger("uvicorn").handlers = [InterceptHandler()]
"""

import logging
import sys
from pathlib import Path

from loguru import logger

from core.config import settings

# 为 extra[corr_id] 提供默认空值，防止格式字符串在缺少该字段时报错
logger.configure(extra={"corr_id": ""})


def setup_logging() -> None:
    """配置 loguru 双 sink（终端彩色 + NDJSON 文件）。

    调用前会先 ``logger.remove()`` 清空默认 handler，
    防止 uvicorn reload 导致重复注册。
    """
    # 清空默认 handler，防止 uvicorn reload 重复
    logger.remove()

    # === Sink 1: 终端彩色 ===
    console_format = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[corr_id]:15.15}</cyan> | "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stderr,
        format=console_format,
        level=settings.log_level.upper(),
        colorize=True,
    )

    # === Sink 2: NDJSON 文件（每日轮转，保留 7 天） ===
    ndjson_path = (
        Path(__file__).resolve().parent.parent
        / "logs"
        / "app_{time:YYYY-MM-DD}.ndjson"
    )
    ndjson_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(ndjson_path),
        format="{extra[ndjson]}",
        level="DEBUG",
        rotation="00:00",
        retention="7 days",
        serialize=True,
        encoding="utf-8",
    )


class InterceptHandler(logging.Handler):
    """将标准 ``logging`` 记录转发到 loguru。

    用法示例：
        import logging
        logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]
        logging.getLogger("uvicorn.error").handlers = [InterceptHandler()]
    """

    def emit(self, record: logging.LogRecord) -> None:
        """转发 ``LogRecord`` 到 loguru。"""
        # 获取对应的 loguru 级别名
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 跳过 logging 内部帧，定位到真正的调用者
        frame, depth = logging.currentframe(), 0
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def get_logger(name: str):
    """创建模块专属的 loguru logger。

    用法：
        logger = get_logger(__name__)
        logger.info("module initialized")
    """
    return logger.bind(module=name)

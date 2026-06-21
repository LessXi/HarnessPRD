"""Debug API — 诊断工具端点（开发环境使用，无认证）。

端点：
- POST /api/debug/log           接收前端批量日志
- GET  /api/debug/session/{id}  聚合 session 诊断数据
- POST /api/debug/log-level     动态调整日志级别
"""

import json
import sys
from collections import OrderedDict
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from core.config import settings
from core.logging_config import setup_logging

router = APIRouter(prefix="/api/debug", tags=["debug"])


# ======================== 数据模型 ========================


class LogEntry(BaseModel):
    """单条前端日志记录"""

    timestamp: float
    level: str = "info"
    source: str
    data: dict = {}
    session_id: str


class BatchLogRequest(BaseModel):
    """批量日志请求体"""

    logs: List[LogEntry]


class LogLevelRequest(BaseModel):
    """动态调级请求体"""

    level: str  # DEBUG / INFO / WARNING / ERROR


# ======================== 内存存储 ========================


class DebugStore:
    """内存 Debug 数据存储（FIFO 淘汰 + 大小限制）。

    设计说明：
    - 最多保留 ``MAX_SESSIONS`` 个 session
    - 每个 session 日志超 ``MAX_SESSION_SIZE`` 字节时截断为最近 50 条
    - 用 ``OrderedDict`` 实现 FIFO 淘汰（新 session 插入末尾，淘汰从头部）
    """

    MAX_SESSIONS = 50
    MAX_SESSION_SIZE = 100_000  # bytes
    TRUNCATE_KEEP = 50  # 截断后保留条数

    def __init__(self):
        self._store: OrderedDict[str, dict] = OrderedDict()

    def add_log(self, session_id: str, log_entry: dict) -> None:
        """追加一条日志到指定 session。

        如果 session 不存在则创建；达到容量限制时按 FIFO 淘汰。
        """
        if session_id not in self._store:
            if len(self._store) >= self.MAX_SESSIONS:
                self._store.popitem(last=False)  # 淘汰最旧 session
            self._store[session_id] = {"logs": [], "total_size": 0}

        session = self._store[session_id]
        session["logs"].append(log_entry)
        # 估算新增字节（JSON 序列化长度）
        session["total_size"] += len(json.dumps(log_entry, ensure_ascii=False))

        # 超出总大小限制 → 保留最近 TRUNCATE_KEEP 条
        if session["total_size"] > self.MAX_SESSION_SIZE:
            session["logs"] = session["logs"][-self.TRUNCATE_KEEP :]
            # 重新估算总大小（近似值）
            session["total_size"] = sum(
                len(json.dumps(e, ensure_ascii=False)) for e in session["logs"]
            )

    def get_session(self, session_id: str) -> Optional[dict]:
        """获取 session 诊断数据，不存在时返回 None。"""
        session = self._store.get(session_id)
        if session is None:
            return None
        return {
            "session_id": session_id,
            "logs": session["logs"],
            "count": len(session["logs"]),
            "total_size_bytes": session["total_size"],
        }

    def clear(self) -> None:
        """清空所有诊断数据（测试辅助方法）。"""
        self._store.clear()


# 全局单例
debug_store = DebugStore()


# ======================== 端点 ========================


@router.post("/log")
async def receive_frontend_logs(batch: BatchLogRequest):
    """接收前端批量日志并存入内存 store。"""
    for entry in batch.logs:
        debug_store.add_log(entry.session_id, entry.model_dump())
    logger.debug("Received {n} frontend log entries", n=len(batch.logs))
    return {"received": len(batch.logs)}


@router.get("/session/{session_id}")
async def get_session_debug_data(session_id: str):
    """聚合指定 session 的诊断数据。"""
    data = debug_store.get_session(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return data


@router.post("/log-level")
async def set_log_level(req: LogLevelRequest):
    """动态调整日志级别（DEBUG / INFO / WARNING / ERROR）。

    实现方式：移除所有 loguru handler 后用新级别重新 setup。
    同时更新 ``settings.log_level`` 以保持后续调用一致。
    """
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
    level_upper = req.level.upper()
    if level_upper not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid log level: {req.level}. Must be one of {sorted(valid_levels)}",
        )

    previous = settings.log_level

    # 更新配置 + 重建 sink
    settings.log_level = level_upper
    setup_logging(level=level_upper)

    logger.bind(event="config_change").warning(
        "Log level changed: {previous} -> {current}",
        previous=previous,
        current=level_upper,
    )
    return {"previous": previous, "current": level_upper}

"""会话管理路由 — 仅保留 GET /api/questions"""

from pathlib import Path
import json

from fastapi import APIRouter

router = APIRouter(tags=["questions"])

# 加载表单配置供前端使用
_QUESTIONS_CONFIG_PATH = Path(__file__).resolve().parent.parent / "core" / "questions_config.json"
with open(_QUESTIONS_CONFIG_PATH, encoding="utf-8") as _f:
    _questions_config = json.load(_f)


@router.get("/api/questions")
async def get_questions():
    """返回表单配置，前端据此动态渲染表单"""
    return _questions_config

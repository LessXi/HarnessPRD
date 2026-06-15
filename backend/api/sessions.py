"""会话管理路由"""

from pathlib import Path
import json

from fastapi import APIRouter, HTTPException

from api.schemas import SessionCreatedResponse, SessionSummary
from core.state import FormData
from services.session_service import create_session, get_session, list_sessions

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# 加载表单配置供前端使用
_QUESTIONS_CONFIG_PATH = Path(__file__).resolve().parent.parent / "core" / "questions_config.json"
with open(_QUESTIONS_CONFIG_PATH, encoding="utf-8") as _f:
    _questions_config = json.load(_f)


@router.get("/questions")
async def get_questions():
    """返回表单配置，前端据此动态渲染表单"""
    return _questions_config


@router.post("", response_model=SessionCreatedResponse)
async def create_session_endpoint(data: FormData):
    """创建 Session + 提交表单 → 进入 ai_dialogue 状态"""
    try:
        session = create_session(data)
        return {
            "session_id": session.session_id,
            "current_state": session.current_state.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[SessionSummary])
async def list_sessions_endpoint(limit: int = 10):
    """最近会话列表"""
    return list_sessions(limit)


@router.get("/{session_id}")
async def get_session_endpoint(session_id: str):
    """获取完整 SessionData（刷新恢复用）"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump(mode="json")

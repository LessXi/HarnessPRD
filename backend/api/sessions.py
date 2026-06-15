"""会话管理路由"""

from fastapi import APIRouter, HTTPException

from core.state import FormData
from services.session_service import create_session, get_session, list_sessions

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("")
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


@router.get("")
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

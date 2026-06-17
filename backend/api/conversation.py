"""AI 对话路由：消息 + SSE 流 + 摘要

两层架构：
- Service 层（conversation_service.py）生成流式内容
- Route 层（本文件）把异步流包装成标准 SSE 响应

SSE 事件格式：
  data: {"event":"chunk","content":"<token>"}
  data: {"event":"done"}
  data: {"event":"error","content":"<message>"}
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.schemas import MessageRequest, SummaryResponse, ConfirmResponse
from api.sse_utils import SSE_HEADERS, make_sse_stream
from core.state import ChatMessage, StateEnum
from services.conversation_service import ConversationService
from services.session_service import get_session, update_session

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["conversation"])

_conversation = ConversationService()

# ========================================================================
# SSE 常量 & 工具函数
# ========================================================================

# ========================================================================
# 消息
# ========================================================================


@router.post("/messages")
async def send_message(session_id: str, data: MessageRequest):
    """发送用户消息（非流式，只追加记录；SSE 走 /start-stream 和 /continue-stream）"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.current_state != StateEnum.AI_DIALOGUE:
        raise HTTPException(400, f"当前状态不允许发送消息: {session.current_state.value}")

    msg = ChatMessage(
        role="user",
        content=data.content,
        timestamp=datetime.now(timezone.utc),
    )
    session.chat_messages.append(msg)
    update_session(session)
    return {"status": "ok"}


@router.get("/messages")
async def get_messages(session_id: str):
    """获取对话历史"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return [m.model_dump(mode="json") for m in session.chat_messages]


# ========================================================================
# SSE 流式端点
# ========================================================================


@router.post("/start-stream")
async def start_stream(session_id: str):
    """SSE 端点：AI 主动破冰问候

    首次进入对话页时调用，无需请求体。
    调 ConversationService.start_conversation_stream() 并包装为标准 SSE 事件。
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.current_state != StateEnum.AI_DIALOGUE:
        raise HTTPException(400, f"当前状态不允许流式对话: {session.current_state.value}")
    if len(session.chat_messages) > 0:
        raise HTTPException(400, "会话已有历史消息，请使用 /continue-stream")

    stream = _conversation.start_conversation_stream(session)
    return StreamingResponse(
        make_sse_stream(stream),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/continue-stream")
async def continue_stream(session_id: str, data: MessageRequest):
    """SSE 端点：AI 接续回复

    用户已通过 POST /messages 追加消息后调用。
    请求体：{"content": "用户消息"}
    调 ConversationService.continue_conversation_stream() 并包装为标准 SSE 事件。
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.current_state != StateEnum.AI_DIALOGUE:
        raise HTTPException(400, f"当前状态不允许流式对话: {session.current_state.value}")
    if len(session.chat_messages) == 0:
        raise HTTPException(400, "会话无历史消息，请使用 /start-stream")

    stream = _conversation.continue_conversation_stream(session, data.content)
    return StreamingResponse(
        make_sse_stream(stream),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


# ========================================================================
# 摘要
# ========================================================================


@router.post("/summary/generate", response_model=SummaryResponse)
async def generate_summary(session_id: str):
    """触发需求摘要生成（非流式）"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    summary = await _conversation.generate_summary(session)
    return {"summary": summary}


@router.post("/summary/confirm", response_model=ConfirmResponse)
async def confirm_summary(session_id: str):
    """确认摘要 → 进入 generating_prd 状态"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if not session.requirements_summary:
        raise HTTPException(400, "请先生成需求摘要")

    session.summary_confirmed = True
    update_session(session)
    return {"status": "ok", "next_state": session.current_state.value}


@router.post("/summary/reject")
async def reject_summary(session_id: str):
    """拒绝摘要 → 继续对话"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    session.requirements_summary = None
    update_session(session)
    return {"status": "ok", "message": "继续补充需求"}


# ========================================================================
# 跳过对话
# ========================================================================


@router.post("/dialogues/skip", response_model=ConfirmResponse)
async def skip_dialogue(session_id: str):
    """跳过对话兜底分支"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    session.skip_dialogue = True
    session.current_state = StateEnum.GENERATING_PRD
    update_session(session)
    return {"status": "ok", "next_state": session.current_state.value}

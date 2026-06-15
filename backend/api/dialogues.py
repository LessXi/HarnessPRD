"""AI 对话路由：消息 + 摘要 + SSE"""

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.schemas import MessageRequest, SummaryResponse, ConfirmResponse

from core.state import ChatMessage, StateEnum
from services.llm_service import stream_chat
from services.session_service import get_session, update_session

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["dialogues"])


# ========== 消息 ==========

@router.post("/messages")
async def send_message(session_id: str, data: MessageRequest):
    """发送用户消息（非流式，只追加记录；SSE 连接走 /messages/stream）"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.current_state != StateEnum.AI_DIALOGUE:
        raise HTTPException(400, f"当前状态不允许发送消息: {session.current_state.value}")

    # 追加用户消息
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


@router.get("/messages/stream")
async def stream_messages(session_id: str):
    """SSE 端点：流式接收 AI 回复"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    system_prompt = _build_chat_system_prompt(session)
    last_user_msg = session.chat_messages[-1].content if session.chat_messages else ""

    async def _event_stream():
        full_response = ""
        async for chunk in stream_chat(system_prompt, last_user_msg):
            full_response += chunk
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"

        # 追加 AI 回复到历史
        ai_msg = ChatMessage(
            role="assistant",
            content=full_response,
            timestamp=datetime.now(timezone.utc),
        )
        session.chat_messages.append(ai_msg)
        update_session(session)

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ========== 摘要 ==========

@router.post("/summary/generate", response_model=SummaryResponse)
async def generate_summary(session_id: str):
    """触发需求摘要生成"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    from services.llm_service import get_llm
    from langchain.schema import HumanMessage, SystemMessage

    prompt = _build_summary_prompt(session)
    llm = get_llm()
    result = await llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content="请根据以上对话生成需求摘要"),
    ])
    session.requirements_summary = result.content if hasattr(result, "content") else str(result)
    update_session(session)
    return {"summary": session.requirements_summary}


@router.post("/summary/confirm", response_model=ConfirmResponse)
async def confirm_summary(session_id: str):
    """确认摘要 → 进入 generating_prd 状态"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if not session.requirements_summary:
        raise HTTPException(400, "请先生成需求摘要")

    session.summary_confirmed = True
    session.current_state = StateEnum.GENERATING_PRD
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


# ========== 跳过对话 ==========

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


# ========== 内部辅助 ==========

def _build_chat_system_prompt(session) -> str:
    """构造对话系统 Prompt（含表单上下文 + 历史）"""
    form = session.form_data
    base = f"""你是一位资深 AI 产品经理，正在帮用户澄清产品需求。

产品名称: {form.product_name if form else '未知'}
一句话定义: {form.one_liner if form else ''}
核心痛点: {form.problem_statement if form else ''}
目标用户: {form.target_users if form else ''}
MVP 功能: {', '.join(form.mvp_features) if form else ''}

请根据以上信息，向用户追问细节。"""
    return base


def _build_summary_prompt(session) -> str:
    """构造摘要 Prompt"""
    form = session.form_data
    chat_log = "\n".join(
        f"{'用户' if m.role == 'user' else 'AI'}: {m.content}"
        for m in session.chat_messages
    )
    return f"""请根据以下产品信息和对话历史，生成结构化的需求摘要（JSON 格式），
包含：产品概述、核心功能、目标用户、技术偏好、关键决策点。

## 产品信息
产品名称: {form.product_name if form else ''}
一句话定义: {form.one_liner if form else ''}
核心痛点: {form.problem_statement if form else ''}
目标用户: {form.target_users if form else ''}
MVP 功能: {', '.join(form.mvp_features) if form else ''}

## 对话历史
{chat_log}"""

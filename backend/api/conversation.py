"""AI 对话路由：SSE 流式对话 + 摘要生成

无状态设计：每个请求携带完整上下文。
SSE 事件格式：
  data: {"event":"chunk","content":"<token>"}
  data: {"event":"done"}
  data: {"event":"error","content":"<message>"}
"""

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.schemas import ChatRequest, SummaryRequest, SummaryResponse
from api.sse_utils import SSE_HEADERS, make_sse_stream
from services.conversation_service import chat_stream, generate_summary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["conversation"])


@router.post("/api/chat/stream")
async def chat_stream_endpoint(data: ChatRequest):
    """SSE 端点：流式对话（合并 start/continue）。

    - history 为空 + 无额外 user_message → AI 破冰问候
    - history 非空 → AI 接续回复（user_message 应为 history 最后一条）
    """
    session_id = data.session_id or "unknown"
    logger.info(f"[{session_id}] chat/stream request, history_len={len(data.history)}")

    # 从 history 最后一条提取 user_message（如果有的话）
    user_message = ""
    history_for_service = data.history
    if data.history and data.history[-1].get("role") == "user":
        user_message = data.history[-1].get("content", "")
        history_for_service = data.history[:-1]

    async def _stream():
        full_response = ""
        try:
            async for chunk in chat_stream(
                form_data=data.form_data,
                history=history_for_service,
                user_message=user_message,
            ):
                full_response += chunk
                yield f"data: {json.dumps({'event': 'chunk', 'content': chunk})}\n\n"

            # done 事件携带完整 AI 回复，前端可据此更新 history
            yield f"data: {json.dumps({'event': 'done', 'assistant_content': full_response})}\n\n"
        except Exception as e:
            logger.exception(f"[{session_id}] chat stream error")
            yield f"data: {json.dumps({'event': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/api/summary/generate", response_model=SummaryResponse)
async def generate_summary_endpoint(data: SummaryRequest):
    """需求摘要生成（非流式）。"""
    session_id = data.session_id or "unknown"
    logger.info(f"[{session_id}] summary/generate request")

    summary = await generate_summary(
        form_data=data.form_data,
        history=data.history,
    )
    return {"summary": summary}

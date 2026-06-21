"""SSE 流式响应工具 — conversation 和 documents 路由共用"""

import json
from typing import AsyncGenerator

from skill_engine.models import SSEEvent

# 标准 SSE 响应头，禁用缓冲
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Content-Type": "text/event-stream",
}


def _serialize_sse_event(event: SSEEvent) -> str:
    """将 SSEEvent 序列化为 SSE data 行（与前端 readStream 兼容）。

    前端 readStream 依赖以下事件格式：
      data: {"event":"chunk","content":"<token>"}
      data: {"event":"review_result","passed":bool,"issues":[...]}
      data: {"event":"done","content":"<全文>"}
      data: {"event":"error","content":"<message>"}
    """
    if event.event == "chunk":
        return f"data: {json.dumps({'event': 'chunk', 'content': event.content})}\n\n"
    elif event.event == "review_result":
        return f"data: {json.dumps({'event': 'review_result', 'passed': event.passed, 'issues': event.issues})}\n\n"
    elif event.event == "done":
        return f"data: {json.dumps({'event': 'done', 'content': event.content})}\n\n"
    elif event.event == "error":
        return f"data: {json.dumps({'event': 'error', 'content': event.content})}\n\n"
    return f"data: {json.dumps({'event': event.event, 'content': event.content})}\n\n"


async def make_sse_stream(stream: AsyncGenerator[SSEEvent, None]) -> AsyncGenerator[str, None]:
    """将 skill_engine 的 SSEEvent 流包装为标准 SSE data 行。

    支持 event 类型：chunk、review_result、done、error。
    """
    try:
        async for event in stream:
            yield _serialize_sse_event(event)
    except Exception as e:
        yield f"data: {json.dumps({'event': 'error', 'content': str(e)})}\n\n"

"""SSE 流式响应工具 — conversation 和 documents 路由共用"""

import json
from typing import AsyncGenerator

# 标准 SSE 响应头，禁用缓冲
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Content-Type": "text/event-stream",
}


async def make_sse_stream(stream: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    """将 Service 层的流式生成器包装为标准 SSE 事件。

    前端 readStream 依赖以下事件格式：
      data: {"event":"chunk","content":"<token>"}
      data: {"event":"done"}
      data: {"event":"error","content":"<message>"}
    """
    try:
        async for chunk in stream:
            if chunk:
                yield f"data: {json.dumps({'event': 'chunk', 'content': chunk})}\n\n"
        yield f"data: {json.dumps({'event': 'done'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'event': 'error', 'content': str(e)})}\n\n"

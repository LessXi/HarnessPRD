"""文档生成路由：PRD / 接口文档 / 提示词套件

无状态设计：每个请求携带完整上下文。
底层使用 skill_engine，返回 SSEEvent 流。
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

from api.schemas import DocumentRequest, OptimizeRequest, DownloadRequest
from api.sse_utils import SSE_HEADERS
from services.document_service import generate_document_stream, optimize_document_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

DOC_TYPES = {"prd", "api", "prompts"}


def _serialize_sse(event) -> str:
    """将 SSEEvent 序列化为 SSE data 行（与前端 readStream 兼容）。"""
    if event.event == "chunk":
        return f"data: {json.dumps({'event': 'chunk', 'content': event.content})}\n\n"
    elif event.event == "review_result":
        return f"data: {json.dumps({'event': 'review_result', 'passed': event.passed, 'issues': event.issues})}\n\n"
    elif event.event == "done":
        return f"data: {json.dumps({'event': 'done', 'content': event.content})}\n\n"
    elif event.event == "error":
        return f"data: {json.dumps({'event': 'error', 'content': event.content})}\n\n"
    return f"data: {json.dumps({'event': event.event, 'content': event.content})}\n\n"


@router.post("/{doc_type}/stream")
async def stream_document(request: Request, doc_type: str, data: DocumentRequest):
    """SSE 端点：流式生成文档（含自动 review→rewrite 循环）。"""
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, f"不支持的文档类型: {doc_type}")

    session_id = getattr(request.state, "correlation_id", data.session_id or "unknown")
    logger.info(f"[{session_id}] documents/{doc_type}/stream request")

    async def _stream():
        try:
            async for event in generate_document_stream(
                doc_type=doc_type,
                form_data=data.form_data,
                requirements_summary=data.requirements_summary,
                previous_content=data.previous_content,
                prd_content=data.prd_content,
                api_content=data.api_content,
                session_id=session_id,
            ):
                yield _serialize_sse(event)

            # safety fallback — engine 理应 yield done 事件
            # yield f"data: {json.dumps({'event': 'done'})}\n\n"
        except Exception as e:
            logger.exception(f"[{session_id}] document stream error")
            yield f"data: {json.dumps({'event': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/{doc_type}/optimize")
async def optimize_document(request: Request, doc_type: str, data: OptimizeRequest):
    """SSE 端点：流式文档优化（review→rewrite 循环）。"""
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, f"不支持的文档类型: {doc_type}")

    session_id = getattr(request.state, "correlation_id", data.session_id or "unknown")
    logger.info(f"[{session_id}] documents/{doc_type}/optimize request")

    async def _stream():
        try:
            async for event in optimize_document_stream(
                doc_type=doc_type,
                content=data.content,
                form_data=data.form_data,
                requirements_summary=data.requirements_summary,
                prd_content=data.prd_content,
                api_content=data.api_content,
                session_id=session_id,
            ):
                yield _serialize_sse(event)

            # safety fallback
            # yield f"data: {json.dumps({'event': 'done'})}\n\n"
        except Exception as e:
            logger.exception(f"[{session_id}] document optimize error")
            yield f"data: {json.dumps({'event': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/{doc_type}/download")
async def download_document(doc_type: str, data: DownloadRequest):
    """下载文档为 .md 文件。"""
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, f"不支持的文档类型: {doc_type}")

    if not data.content:
        raise HTTPException(400, "文档内容不能为空")

    return PlainTextResponse(
        content=data.content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{doc_type}.md"',
        },
    )

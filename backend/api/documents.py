"""文档生成路由：PRD / 接口文档 / 提示词套件"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.state import StateEnum, session_store
from services.document_service import stream_generate_document, run_review_rewrite, check_streaming_timeout
from services.session_service import get_session, update_session

router = APIRouter(prefix="/api/sessions/{session_id}/documents", tags=["documents"])

# 支持的文档类型
DOC_TYPES = {"prd", "api", "prompts"}

# 状态映射: (generating_state, reviewing_state, next_phase_state)
_STATE_MAP: dict[str, tuple[StateEnum, StateEnum, StateEnum]] = {
    "prd": (StateEnum.GENERATING_PRD, StateEnum.REVIEWING_PRD, StateEnum.GENERATING_API),
    "api": (StateEnum.GENERATING_API, StateEnum.REVIEWING_API, StateEnum.GENERATING_PROMPTS),
    "prompts": (StateEnum.GENERATING_PROMPTS, StateEnum.REVIEWING_PROMPTS, StateEnum.COMPLETED),
}

# 各文档类型生成前允许的当前状态
_GENERATE_ALLOWED: dict[str, StateEnum] = {
    "prd": StateEnum.AI_DIALOGUE,
    "api": StateEnum.REVIEWING_PRD,
    "prompts": StateEnum.REVIEWING_API,
}

# 各文档类型确认前允许的当前状态
_CONFIRM_ALLOWED: dict[str, StateEnum] = {
    "prd": StateEnum.REVIEWING_PRD,
    "api": StateEnum.REVIEWING_API,
    "prompts": StateEnum.REVIEWING_PROMPTS,
}


class ContentInput(BaseModel):
    content: str


# ========== 生成 ==========

@router.post("/{doc_type}/generate")
async def generate_document(session_id: str, doc_type: str):
    """启动文档生成，返回 SSE 流地址"""
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, f"不支持的文档类型: {doc_type}")

    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    gen_state, _, _ = _STATE_MAP[doc_type]
    allowed = _GENERATE_ALLOWED[doc_type]
    if session.current_state != allowed:
        raise HTTPException(400, f"当前状态 {session.current_state.value} 不允许生成 {doc_type}，需要状态 {allowed.value}")

    session.current_state = gen_state
    update_session(session)

    return {
        "status": "ok",
        "stream_url": f"/api/sessions/{session_id}/documents/{doc_type}/stream",
    }


@router.get("/{doc_type}/stream")
async def stream_document(session_id: str, doc_type: str):
    """SSE 端点：流式接收文档内容"""
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, f"不支持的文档类型: {doc_type}")

    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    # 检测断连超时：如果上次 chunk 超过阈值未更新，重置 streaming 后重新生成
    check_streaming_timeout(session, doc_type)

    async def _event_stream():
        async for chunk in stream_generate_document(session, doc_type):
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        yield f"data: {json.dumps({'event': 'stream_complete'})}\n\n"

        # SSE 流结束后自动触发 Review→Rewrite 循环
        await run_review_rewrite(session, doc_type)
        yield f"data: {json.dumps({'event': 'review_complete', 'rounds': getattr(session, doc_type).current_round})}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ========== 查询 ==========

@router.get("/{doc_type}")
async def get_document(session_id: str, doc_type: str):
    """获取文档当前内容"""
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, f"不支持的文档类型: {doc_type}")

    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    doc = getattr(session, doc_type)
    return doc.model_dump(mode="json")


@router.get("/{doc_type}/review-rounds")
async def get_review_rounds(session_id: str, doc_type: str):
    """获取审核轮次历史"""
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, f"不支持的文档类型: {doc_type}")

    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    doc = getattr(session, doc_type)
    return [r.model_dump(mode="json") for r in doc.review_rounds]


# ========== 编辑 ==========

@router.put("/{doc_type}/content")
async def update_document_content(session_id: str, doc_type: str, data: ContentInput):
    """保存用户手动编辑内容"""
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, f"不支持的文档类型: {doc_type}")

    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    doc = getattr(session, doc_type)
    doc.user_edits = data.content
    update_session(session)
    return {"status": "ok"}


# ========== 下载 ==========

@router.get("/{doc_type}/download")
async def download_document(session_id: str, doc_type: str):
    """下载文档为 .md 文件"""
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, f"不支持的文档类型: {doc_type}")

    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    doc = getattr(session, doc_type)
    content = doc.user_edits or doc.content

    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(
        content=content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{doc_type}.md"',
        },
    )


# ========== 确认 ==========

@router.post("/{doc_type}/confirm")
async def confirm_document(session_id: str, doc_type: str):
    """确认文档完成 → 进入下一阶段"""
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, f"不支持的文档类型: {doc_type}")

    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    doc = getattr(session, doc_type)

    allowed = _CONFIRM_ALLOWED[doc_type]
    if session.current_state != allowed:
        raise HTTPException(400, f"当前状态 {session.current_state.value} 不允许确认，需要状态 {allowed.value}")

    doc.confirmed = True

    _, _, next_state = _STATE_MAP[doc_type]
    session.current_state = next_state
    update_session(session)

    return {
        "status": "ok",
        "next_state": session.current_state.value,
    }

"""文档服务：PRD / 接口文档 / 提示词套件的流式生成与优化

公开方法（4 个）：
- generate_prd_stream         — 根据对话生成 PRD（astream 流式）
- generate_api_docs_stream    — 根据 PRD 生成接口文档（astream 流式）
- generate_prompts_stream     — 根据 PRD + 接口文档生成提示词套件（astream 流式）
- optimize_document_stream    — 文档 Review→Rewrite 优化（astream 流式）

内部引擎：
- _generate_document_stream   — 通用文档生成（3 个公开方法共用）
- run_review_rewrite          — Review→Rewrite 批量循环
"""

from typing import AsyncGenerator, Optional
from datetime import datetime, timezone

from core.config import settings
from core.state import (
    DocumentState,
    ReviewRound,
    SessionData,
    StateEnum,
    session_store,
)
from services.llm_service import load_prompt, stream_generate

DocType = str  # "prd" | "api" | "prompts"


def check_streaming_timeout(session: SessionData, doc_type: DocType) -> bool:
    """检查生成状态是否超时。

    如果 streaming=True 且 last_chunk_at 超过 settings.sse_timeout_seconds 未更新，
    判定为断连，重置 streaming 并返回 True。
    """
    key = _DOC_TYPE_MAP[doc_type][0]
    doc: DocumentState = getattr(session, key)
    if doc.streaming and doc.last_chunk_at:
        elapsed = (datetime.now(timezone.utc) - doc.last_chunk_at).total_seconds()
        if elapsed > settings.sse_timeout_seconds:
            doc.streaming = False
            session_store.update(session)
            return True
    return False


_DOC_TYPE_MAP = {
    "prd": ("prd", StateEnum.GENERATING_PRD, StateEnum.REVIEWING_PRD, "backend/prompts/generate_prd.jinja2"),
    "api": ("api", StateEnum.GENERATING_API, StateEnum.REVIEWING_API, "backend/prompts/generate_api.jinja2"),
    "prompts": ("prompts", StateEnum.GENERATING_PROMPTS, StateEnum.REVIEWING_PROMPTS, "backend/prompts/generate_prompts.jinja2"),
}


# ========================================================================
# 公开方法（Clean Architecture — 语义化 API）
# ========================================================================


async def generate_prd_stream(session: SessionData) -> AsyncGenerator[str, None]:
    """流式生成 PRD 文档。

    context: form_data + requirements_summary
    完成后 session 进入 GENERATING_PRD → REVIEWING_PRD 状态。
    """
    async for chunk in _generate_document_stream(session, "prd"):
        yield chunk


async def generate_api_docs_stream(session: SessionData) -> AsyncGenerator[str, None]:
    """流式生成接口文档。

    context: form_data + requirements_summary + prd_content
    完成后 session 进入 GENERATING_API → REVIEWING_API 状态。
    """
    async for chunk in _generate_document_stream(session, "api"):
        yield chunk


async def generate_prompts_stream(session: SessionData) -> AsyncGenerator[str, None]:
    """流式生成提示词套件。

    context: form_data + requirements_summary + prd_content + api_content
    完成后 session 进入 GENERATING_PROMPTS → REVIEWING_PROMPTS 状态。
    """
    async for chunk in _generate_document_stream(session, "prompts"):
        yield chunk


async def optimize_document_stream(
    session: SessionData, doc_type: DocType
) -> AsyncGenerator[str, None]:
    """流式 Review→Rewrite 优化。

    对指定文档类型执行审核 + 逐 round 流式输出改写内容。
    最多 max_review_rounds 轮，审核通过后提前终止。
    """
    key, gen_state, review_state, _ = _DOC_TYPE_MAP[doc_type]
    doc: DocumentState = getattr(session, key)
    max_rounds = settings.max_review_rounds

    while doc.current_round < max_rounds:
        # --- Review ---
        review_system_prompt = _build_review_prompt(session, doc_type)
        review_result = await _call_llm_once(review_system_prompt)

        has_issues = _has_issues(review_result)
        if not has_issues:
            doc.review_rounds.append(ReviewRound(
                round_number=doc.current_round + 1,
                review_content=review_result,
                rewrite_content=None,
            ))
            break

        # --- Rewrite（流式） ---
        rewrite_prompt = _build_rewrite_prompt(session, doc_type, review_result)
        rewrite_content = ""
        async for chunk in stream_generate(rewrite_prompt):
            rewrite_content += chunk
            doc.content = rewrite_content
            yield chunk  # 逐 token 输出改写内容

        doc.current_round += 1
        doc.review_rounds.append(ReviewRound(
            round_number=doc.current_round,
            review_content=review_result,
            rewrite_content=rewrite_content,
        ))

        doc.streaming = False

    session.current_state = review_state
    session_store.update(session)


# ========================================================================
# 内部引擎
# ========================================================================


async def _generate_document_stream(
    session: SessionData, doc_type: DocType
) -> AsyncGenerator[str, None]:
    """通用文档生成引擎（3 个公开方法共用）。

    流程：加载 Prompt → astream 流式生成 → 写 session → 状态切换。
    完成后自动触发 Review→Rewrite 循环（调用 run_review_rewrite）。
    """
    key, gen_state, _, prompt_name = _DOC_TYPE_MAP[doc_type]
    doc: DocumentState = getattr(session, key)

    # 更新状态
    session.current_state = gen_state
    doc.streaming = True
    session_store.update(session)

    # 加载 Prompt
    prompt_kwargs = _build_prompt_kwargs(session, doc_type)
    system_prompt = load_prompt(prompt_name, **prompt_kwargs)

    # 流式写入
    full_content = ""
    async for chunk in stream_generate(system_prompt):
        full_content += chunk
        doc.content = full_content
        doc.last_chunk_at = datetime.now(timezone.utc)
        session_store.update(session)
        yield chunk

    # SSE 完成 → 自动进入 review 状态
    doc.streaming = False
    _, _, review_state, _ = _DOC_TYPE_MAP[doc_type]
    session.current_state = review_state
    session_store.update(session)


async def run_review_rewrite(session: SessionData, doc_type: DocType) -> None:
    """系统自动执行 Review→Rewrite 循环（批量，非流式）。

    在 reviewing_X 状态被系统内部触发，不在 API 路由层暴露。
    如需流式输出优化过程，请使用 optimize_document_stream。
    """
    async for _ in optimize_document_stream(session, doc_type):
        pass  # 批量模式：丢弃流式输出，只关心最终结果


# ========================================================================
# 内部工具函数
# ========================================================================


def _build_prompt_kwargs(session: SessionData, doc_type: DocType) -> dict:
    """构造 Prompt 渲染所需的上下文"""
    kwargs: dict = {
        "form_data": session.form_data.model_dump() if session.form_data else {},
        "requirements_summary": session.requirements_summary or "",
    }
    if doc_type in ("api", "prompts"):
        kwargs["prd_content"] = session.prd.content
    if doc_type == "prompts":
        kwargs["api_content"] = session.api.content
    return kwargs


def _build_review_prompt(session: SessionData, doc_type: DocType) -> str:
    """构造审核 Prompt（从 Jinja2 模板加载）"""
    doc = getattr(session, _DOC_TYPE_MAP[doc_type][0])
    return load_prompt("backend/prompts/doc_review.jinja2",
        doc_type=doc_type,
        content=doc.content,
    )


def _build_rewrite_prompt(session: SessionData, doc_type: DocType, review: str) -> str:
    """构造改写 Prompt（从 Jinja2 模板加载）"""
    key = _DOC_TYPE_MAP[doc_type][0]
    doc = getattr(session, key)
    prompt_name = _DOC_TYPE_MAP[doc_type][3]
    base_prompt = load_prompt(prompt_name, **_build_prompt_kwargs(session, doc_type))
    return load_prompt("backend/prompts/doc_rewrite.jinja2",
        base_prompt=base_prompt,
        previous_content=doc.content,
        review=review,
    )


def _has_issues(review_result: str) -> bool:
    """判断审核结果是否发现问题"""
    return "审核通过" not in review_result


async def _call_llm_once(system_prompt: str) -> str:
    """非流式 LLM 调用（用于 Review）"""
    from langchain.schema import SystemMessage
    from services.llm_service import get_llm
    llm = get_llm()
    messages = [SystemMessage(content=system_prompt)]
    result = await llm.ainvoke(messages)
    return result.content if hasattr(result, "content") else str(result)

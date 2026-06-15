"""文档服务：文档生成 + Review→Rewrite 循环"""

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


async def stream_generate_document(
    session: SessionData, doc_type: DocType
) -> AsyncGenerator[str, None]:
    """流式生成文档初稿，内容直接写入 session 的对应 DocumentState"""
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
    """系统自动执行 Review→Rewrite 循环（最多 max_review_rounds 轮）

    在 reviewing_X 状态被系统内部触发，不在 API 路由层暴露。
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
            # 审核通过，无需改写
            doc.review_rounds.append(ReviewRound(
                round_number=doc.current_round + 1,
                review_content=review_result,
                rewrite_content=None,
            ))
            break

        # --- Rewrite ---
        rewrite_prompt = _build_rewrite_prompt(session, doc_type, review_result)
        rewrite_content = ""
        async for chunk in stream_generate(rewrite_prompt):
            rewrite_content += chunk
            doc.content = rewrite_content

        doc.current_round += 1
        doc.review_rounds.append(ReviewRound(
            round_number=doc.current_round,
            review_content=review_result,
            rewrite_content=rewrite_content,
        ))

        # 重置 streaming 标志
        doc.streaming = False

    # 循环结束，确保状态为 reviewing_X
    session.current_state = review_state
    session_store.update(session)


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
    """构造审核 Prompt（根据 doc_type 不同）"""
    doc = getattr(session, _DOC_TYPE_MAP[doc_type][0])
    return f"""你是一位资深文档审核专家。请审核以下{doc_type}文档的质量。
检查项：完整性、一致性、清晰度、可执行性。
如果发现问题，逐条列出问题位置和修改建议。
如果没有问题，输出："审核通过"。

文档内容：
{doc.content}"""


def _build_rewrite_prompt(session: SessionData, doc_type: DocType, review: str) -> str:
    """构造改写 Prompt"""
    key = _DOC_TYPE_MAP[doc_type][0]
    doc = getattr(session, key)
    prompt_name = _DOC_TYPE_MAP[doc_type][3]
    base_prompt = load_prompt(prompt_name, **_build_prompt_kwargs(session, doc_type))
    return f"""{base_prompt}

---

## 上一版文档
{doc.content}

## 审核意见
{review}

请根据以上审核意见修改文档，输出完整的新版文档。"""


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

"""文档服务：PRD / 接口文档 / 提示词套件的流式生成与优化

无状态设计：所有方法从参数获取数据，不引用 session_store。
"""

from typing import Any, AsyncGenerator

from loguru import logger

from core.error_classifier import classify_error
from services.llm_service import load_prompt, stream_generate


DocType = str  # "prd" | "api" | "prompts"

_DOC_TEMPLATES: dict[str, str] = {
    "prd": "backend/prompts/generate_prd.jinja2",
    "api": "backend/prompts/generate_api.jinja2",
    "prompts": "backend/prompts/generate_prompts.jinja2",
}


# ========================================================================
# 公开方法
# ========================================================================


async def generate_document_stream(
    doc_type: DocType,
    form_data: dict[str, Any],
    requirements_summary: str,
    *,
    previous_content: str = "",
    prd_content: str = "",
    api_content: str = "",
    session_id: str = "",
) -> AsyncGenerator[str, None]:
    """流式生成文档。

    Args:
        doc_type: "prd" | "api" | "prompts"
        form_data: 表单数据字典
        requirements_summary: 需求摘要
        previous_content: 已有内容（续写场景）
        prd_content: PRD 内容（api/prompts 生成时需要）
        api_content: 接口文档内容（prompts 生成时需要）
        session_id: 会话 ID（用于 LangSmith metadata 追踪）
    """
    prompt_kwargs = _build_prompt_kwargs(
        form_data, requirements_summary,
        doc_type=doc_type,
        prd_content=prd_content,
        api_content=api_content,
        previous_content=previous_content,
    )

    prompt_name = _DOC_TEMPLATES[doc_type]
    system_prompt = load_prompt(prompt_name, **prompt_kwargs)

    logger.bind(event="doc_generation_start").info("Generating {doc_type}", doc_type=doc_type)
    try:
        async for chunk in stream_generate(system_prompt, session_id=session_id, doc_type=doc_type):
            yield chunk
    except Exception as e:
        category = classify_error(e)
        logger.bind(event="llm_error").error("LLM call failed: {error} [{cat}]", error=str(e), cat=category.value)
        raise
    logger.bind(event="doc_generation_complete").info("Generated {doc_type}", doc_type=doc_type)


async def optimize_document_stream(
    doc_type: DocType,
    content: str,
    form_data: dict[str, Any],
    requirements_summary: str,
    *,
    prd_content: str = "",
    api_content: str = "",
    session_id: str = "",
) -> AsyncGenerator[str, None]:
    """流式 Review→Rewrite 优化。

    对指定文档执行审核 + 逐轮流式输出改写内容。
    最多 max_review_rounds 轮，审核通过后提前终止。
    """
    from core.config import settings

    max_rounds = settings.max_review_rounds
    current_content = content

    for round_num in range(max_rounds):
        logger.bind(event="doc_optimization_round").info("Round {round}", round=round_num + 1)

        # --- Review ---
        review_prompt = _build_review_prompt(doc_type, current_content)
        review_result = await _call_llm_once(review_prompt, session_id=session_id, doc_type=f"{doc_type}_review")

        has_issues = _has_issues(review_result)
        if not has_issues:
            # 审核通过，输出当前内容
            yield current_content
            return

        # --- Rewrite（流式） ---
        rewrite_prompt = _build_rewrite_prompt(
            doc_type, current_content, review_result,
            form_data=form_data,
            requirements_summary=requirements_summary,
            prd_content=prd_content,
            api_content=api_content,
        )

        rewritten = ""
        try:
            async for chunk in stream_generate(rewrite_prompt, session_id=session_id, doc_type=f"{doc_type}_rewrite"):
                rewritten += chunk
                yield chunk
        except Exception as e:
            category = classify_error(e)
            logger.bind(event="llm_error").error("LLM call failed: {error} [{cat}]", error=str(e), cat=category.value)
            raise

        current_content = rewritten


# ========================================================================
# 内部工具函数
# ========================================================================


def _build_prompt_kwargs(
    form_data: dict[str, Any],
    requirements_summary: str,
    *,
    doc_type: DocType,
    prd_content: str = "",
    api_content: str = "",
    previous_content: str = "",
) -> dict[str, Any]:
    """构造 Prompt 渲染所需的上下文。"""
    kwargs: dict[str, Any] = {
        "form_data": form_data,
        "requirements_summary": requirements_summary,
        "previous_content": previous_content,
    }
    if doc_type in ("api", "prompts"):
        kwargs["prd_content"] = prd_content
    if doc_type == "prompts":
        kwargs["api_content"] = api_content
    return kwargs


def _build_review_prompt(doc_type: DocType, content: str) -> str:
    """构造审核 Prompt。"""
    return load_prompt(
        "backend/prompts/doc_review.jinja2",
        doc_type=doc_type,
        content=content,
    )


def _build_rewrite_prompt(
    doc_type: DocType,
    content: str,
    review: str,
    *,
    form_data: dict[str, Any],
    requirements_summary: str,
    prd_content: str = "",
    api_content: str = "",
) -> str:
    """构造改写 Prompt。"""
    prompt_name = _DOC_TEMPLATES[doc_type]
    base_prompt = load_prompt(
        prompt_name,
        **_build_prompt_kwargs(
            form_data, requirements_summary,
            doc_type=doc_type,
            prd_content=prd_content,
            api_content=api_content,
        ),
    )
    return load_prompt(
        "backend/prompts/doc_rewrite.jinja2",
        base_prompt=base_prompt,
        previous_content=content,
        review=review,
    )


def _has_issues(review_result: str) -> bool:
    """判断审核结果是否发现问题。"""
    return "审核通过" not in review_result


async def _call_llm_once(
    system_prompt: str,
    *,
    session_id: str = "",
    doc_type: str = "",
) -> str:
    """非流式 LLM 调用（用于 Review）。"""
    from langchain.schema import SystemMessage
    from services.llm_service import get_llm

    llm = get_llm()
    config = {}
    if session_id:
        config = {"metadata": {"session_id": session_id, "doc_type": doc_type}}
    logger.bind(event="llm_call_start").info("LLM call started ({doc})", doc=doc_type)
    try:
        result = await llm.ainvoke([SystemMessage(content=system_prompt)], config=config)
    except Exception as e:
        category = classify_error(e)
        logger.bind(event="llm_error").error("LLM call failed: {error} [{cat}]", error=str(e), cat=category.value)
        raise
    logger.bind(event="llm_call_complete").info("LLM call completed")
    return result.content if isinstance(result.content, str) else str(result.content)

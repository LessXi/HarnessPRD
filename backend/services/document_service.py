"""文档服务：PRD / 接口文档 / 提示词套件的流式生成与优化

无状态设计：所有方法从参数获取数据，不引用 session_store。
Skill-Driven：底层调用 skill_engine 执行 generate→review→rewrite 循环。
"""

from typing import Any, AsyncGenerator

from loguru import logger

from skill_engine.engine import SkillEngine
from skill_engine.loader import SkillLoader
from skill_engine.models import SSEEvent
from services import llm_service as llm_service_module


DocType = str  # "prd" | "api" | "prompts"

# ---- 全局 skill engine 实例 ----
_skill_loader: SkillLoader | None = None
_skill_engine: SkillEngine | None = None


def init_skill_engine(skills_dir: str) -> None:
    """全局初始化 SkillLoader 和 SkillEngine。

    Args:
        skills_dir: skill .md 文件所在目录路径（如 "backend/skills"）。
    """
    global _skill_loader, _skill_engine
    _skill_loader = SkillLoader(skills_dir)
    _skill_engine = SkillEngine(llm_service_module)
    logger.bind(event="skill_engine_init").info(
        "SkillEngine initialized with {n} skills from {dir}",
        n=len(_skill_loader.list_skills()),
        dir=skills_dir,
    )


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
) -> AsyncGenerator[SSEEvent, None]:
    """流式生成文档（通过 Skill Engine）。

    Args:
        doc_type: "prd" | "api" | "prompts"
        form_data: 表单数据字典
        requirements_summary: 需求摘要
        previous_content: 已有内容（续写场景）
        prd_content: PRD 内容（api/prompts 生成时需要）
        api_content: 接口文档内容（prompts 生成时需要）
        session_id: 会话 ID（用于 LangSmith metadata 追踪，由 engine 透传）

    Yields:
        SSEEvent: chunk / review_result / done / error 事件。
    """
    if _skill_engine is None or _skill_loader is None:
        raise RuntimeError("SkillEngine 未初始化，请先调用 init_skill_engine()")

    skill_name = f"{doc_type}-generate"
    skill = _skill_loader.get(skill_name)

    context = _build_prompt_kwargs(
        form_data, requirements_summary,
        doc_type=doc_type,
        prd_content=prd_content,
        api_content=api_content,
        previous_content=previous_content,
    )
    context["session_id"] = session_id
    context["doc_type"] = doc_type

    logger.bind(event="doc_generation_start").info(
        "Generating {doc_type} via skill '{skill}'", doc_type=doc_type, skill=skill_name
    )
    async for event in _skill_engine.execute(skill, context):
        yield event
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
) -> AsyncGenerator[SSEEvent, None]:
    """流式 Review→Rewrite 优化（通过 Skill Engine）。

    将已有 ``content`` 作为 ``current_content`` 注入 context，
    engine 跳过 generate 步骤，直接执行 review→rewrite 循环。

    Args:
        doc_type: "prd" | "api" | "prompts"
        content: 已有文档内容（待优化）
        form_data: 表单数据字典
        requirements_summary: 需求摘要
        prd_content: PRD 内容（prompts 优化时需要）
        api_content: 接口文档内容
        session_id: 会话 ID（用于 LangSmith metadata 追踪）

    Yields:
        SSEEvent: chunk / review_result / done / error 事件。
    """
    if _skill_engine is None or _skill_loader is None:
        raise RuntimeError("SkillEngine 未初始化，请先调用 init_skill_engine()")

    skill_name = f"{doc_type}-generate"
    skill = _skill_loader.get(skill_name)

    context = _build_prompt_kwargs(
        form_data, requirements_summary,
        doc_type=doc_type,
        prd_content=prd_content,
        api_content=api_content,
    )
    context["current_content"] = content  # 跳过 generate，直接 review
    context["session_id"] = session_id
    context["doc_type"] = doc_type

    logger.bind(event="doc_optimization_start").info(
        "Optimizing {doc_type} via skill '{skill}'", doc_type=doc_type, skill=skill_name
    )
    async for event in _skill_engine.execute(skill, context):
        yield event
    logger.bind(event="doc_optimization_complete").info("Optimized {doc_type}", doc_type=doc_type)


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




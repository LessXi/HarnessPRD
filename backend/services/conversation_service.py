"""对话服务：Prompt 组装、流式对话、摘要生成

无状态设计：所有方法从参数获取数据，不引用 session_store。
"""

from typing import Any, AsyncGenerator

from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage

from core.field_registry import get_all_fields, is_list_field
from services.llm_service import load_prompt, get_llm


# ========================================================================
# 工具函数
# ========================================================================


def _form_to_kwargs(form_data: dict[str, Any]) -> dict[str, Any]:
    """将表单数据字典转为模板需要的上下文。

    既保留单个字段 key（{{ product_name }} 等向后兼容），
    也提供 form_fields 列表供模板迭代渲染，实现数据驱动。
    """
    kwargs: dict[str, Any] = {}
    form_fields: list[dict] = []
    for field in get_all_fields():
        fid = field["id"]
        label = field.get("label", fid)
        value = form_data.get(fid, "")
        if is_list_field(fid) and isinstance(value, list):
            value = ", ".join(value)
        kwargs[fid] = value or ""
        if value or field.get("required"):
            form_fields.append({"label": label, "value": str(value) if value else ""})
    kwargs["form_fields"] = form_fields
    return kwargs


def _build_system_prompt(form_data: dict[str, Any]) -> str:
    """构建统一的系统 Prompt。"""
    kwargs = _form_to_kwargs(form_data)
    return load_prompt("backend/prompts/chat_system.jinja2", **kwargs)


def _build_lc_messages(
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
) -> list[BaseMessage]:
    """构建 LangChain 消息列表：System + 历史 + 当前用户消息"""
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    for m in history:
        if m.get("role") == "user":
            messages.append(HumanMessage(content=m.get("content", "")))
        elif m.get("role") == "assistant":
            messages.append(AIMessage(content=m.get("content", "")))
    if user_message:
        messages.append(HumanMessage(content=user_message))
    return messages


# ========================================================================
# 公开方法（无状态）
# ========================================================================


async def chat_stream(
    form_data: dict[str, Any],
    history: list[dict[str, str]],
    user_message: str,
) -> AsyncGenerator[str, None]:
    """流式对话：接收完整上下文，逐 token yield AI 回复。

    - history 为空 + user_message 为空 → AI 破冰问候
    - history 非空 + user_message 非空 → AI 接续回复
    """
    system = _build_system_prompt(form_data)
    messages = _build_lc_messages(system, history, user_message)

    llm = get_llm()
    async for chunk in llm.astream(messages):
        content: str = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
        if content:
            yield content


async def generate_summary(
    form_data: dict[str, Any],
    history: list[dict[str, str]],
) -> str:
    """生成结构化需求摘要（非流式）。"""
    kwargs = _form_to_kwargs(form_data)

    chat_log_lines = []
    for m in history:
        role_label = "用户" if m.get("role") == "user" else "AI"
        chat_log_lines.append(f"[{role_label}] {m.get('content', '')}")
    kwargs["chat_log"] = "\n".join(chat_log_lines)

    summary_prompt = load_prompt("backend/prompts/chat_summary.jinja2", **kwargs)

    llm = get_llm()
    result = await llm.ainvoke([
        SystemMessage(content=summary_prompt),
        HumanMessage(content="请根据以上信息生成需求摘要"),
    ])

    return result.content if isinstance(result.content, str) else str(result.content)

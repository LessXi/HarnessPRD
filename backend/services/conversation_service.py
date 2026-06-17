"""对话服务：Prompt 组装、流式对话、摘要生成

职责：
- format_form_data — 将表单字典转为易读文本
- _build_system_prompt — 渲染统一的 chat_system.jinja2 提示词（始终用同一份）
- _build_lc_messages — 转换为 LangChain 消息格式（System + 历史 + 当前）
- _serialize_messages — 转回前端 {role, content} 格式
- ConversationService 类：
  - start_conversation_stream — AI 主动破冰问候
  - continue_conversation_stream — 接续对话
  - generate_summary — 非流式需求摘要生成
"""

from datetime import datetime, timezone
from typing import AsyncGenerator

from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage

from core.state import ChatMessage, SessionData
from core.field_registry import get_all_fields, is_list_field
from services.llm_service import load_prompt, get_llm
from services.session_service import update_session


# ========================================================================
# 工具函数
# ========================================================================


def format_form_data(session: SessionData) -> str:
    """将表单数据转为易读的纯文本块（供 Prompt 上下文使用）"""
    form = session.form_data
    if not form:
        return "（无表单数据）"

    lines = []
    for field in get_all_fields():
        fid = field["id"]
        label = field.get("label", fid)
        value = getattr(form, fid, "")
        if is_list_field(fid) and isinstance(value, list):
            value = "、".join(value)
        if not value and not field.get("required"):
            continue  # 选填空值不输出
        lines.append(f"{label}：{value}")

    return "\n".join(lines)


def _form_to_kwargs(session: SessionData) -> dict:
    """将表单数据转为模板需要的上下文。

    既保留单个字段 key（{{ product_name }} 等向后兼容），
    也提供 form_fields 列表供模板迭代渲染，实现数据驱动。
    """
    form = session.form_data
    kwargs: dict = {}
    form_fields: list[dict] = []
    if form:
        for field in get_all_fields():
            fid = field["id"]
            label = field.get("label", fid)
            value = getattr(form, fid, "")
            if is_list_field(fid) and isinstance(value, list):
                value = ", ".join(value)
            kwargs[fid] = value or ""
            # 选填空值不加入显示列表
            if value or field.get("required"):
                form_fields.append({"label": label, "value": str(value) if value else ""})
    kwargs["form_fields"] = form_fields
    return kwargs


def _build_system_prompt(session: SessionData) -> str:
    """构建统一的系统 Prompt。

    始终使用 chat_system.jinja2 单一模板，不再区分首次问候/接续对话。
    AI 的角色、任务、行为原则在同一份提示词中定义，对话历史由消息链承载。
    """
    kwargs = _form_to_kwargs(session)
    return load_prompt("backend/prompts/chat_system.jinja2", **kwargs)


def _build_lc_messages(
    session: SessionData,
    user_message: str,
) -> list[BaseMessage]:
    """构建 LangChain 消息列表：System + 历史 Human/AI + 当前 Human"""
    messages: list[BaseMessage] = [
        SystemMessage(content=_build_system_prompt(session)),
    ]
    for m in session.chat_messages:
        if m.role == "user":
            messages.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            messages.append(AIMessage(content=m.content))
    if user_message:
        messages.append(HumanMessage(content=user_message))
    return messages


def _serialize_messages(messages: list[BaseMessage]) -> list[dict]:
    """LangChain BaseMessage → [{role, content}] 前端格式（跳过 SystemMessage）"""
    result = []
    for m in messages:
        if isinstance(m, SystemMessage):
            continue
        role = "user" if isinstance(m, HumanMessage) else "assistant"
        result.append({"role": role, "content": m.content})
    return result


# ========================================================================
# ConversationService
# ========================================================================


class ConversationService:
    """对话服务：Prompt 组装、流式输出、摘要生成"""

    def __init__(self) -> None:
        self._llm = get_llm()

    # ---------- 首次问候 ----------

    async def start_conversation_stream(
        self,
        session: SessionData,
    ) -> AsyncGenerator[str, None]:
        """AI 主动破冰问候。

        在用户首次进入对话页面时调用。
        使用统一的 chat_system.jinja2 提示词 + 表单信息，不含对话历史。

        Yields:
            逐 token 文本块。
        完成后自动将 AI 消息追加到 session.chat_messages 并回写存储。
        """
        if session.chat_messages:
            return  # 已有消息不重新开始

        system = _build_system_prompt(session)
        messages: list[BaseMessage] = [SystemMessage(content=system)]

        full_response = ""
        async for chunk in self._llm.astream(messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            if content:
                full_response += content
                yield content

        # 保存 AI 回复
        ai_msg = ChatMessage(
            role="assistant",
            content=full_response,
            timestamp=datetime.now(timezone.utc),
        )
        session.chat_messages.append(ai_msg)
        update_session(session)

    # ---------- 接续对话 ----------

    async def continue_conversation_stream(
        self,
        session: SessionData,
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """AI 回复用户消息。

        用户已通过 POST /messages 追加消息后调用。
        使用统一的 chat_system.jinja2 提示词 + 完整对话历史。

        Args:
            session: 当前会话
            user_message: 用户刚发送的消息内容

        Yields:
            逐 token 文本块。
        完成后自动将 AI 消息追加到 session.chat_messages 并回写存储。
        """
        messages = _build_lc_messages(session, user_message)

        full_response = ""
        async for chunk in self._llm.astream(messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            if content:
                full_response += content
                yield content

        # 保存 AI 回复
        ai_msg = ChatMessage(
            role="assistant",
            content=full_response,
            timestamp=datetime.now(timezone.utc),
        )
        session.chat_messages.append(ai_msg)
        update_session(session)

    # ---------- 摘要生成 ----------

    async def generate_summary(self, session: SessionData) -> str:
        """生成结构化需求摘要（非流式）。

        使用 chat_summary.jinja2 模板并调用 LLM，
        结果写入 session.requirements_summary 并持久化。
        """
        kwargs = _form_to_kwargs(session)

        # 构造对话日志文本
        chat_log_lines = []
        for m in session.chat_messages:
            role_label = "用户" if m.role == "user" else "AI"
            chat_log_lines.append(f"[{role_label}] {m.content}")
        kwargs["chat_log"] = "\n".join(chat_log_lines)

        summary_prompt = load_prompt("backend/prompts/chat_summary.jinja2", **kwargs)

        result = await self._llm.ainvoke([
            SystemMessage(content=summary_prompt),
            HumanMessage(content="请根据以上信息生成需求摘要"),
        ])

        summary = result.content if hasattr(result, "content") else str(result)
        session.requirements_summary = summary
        update_session(session)
        return summary

"""对话服务：Prompt 组装、流式对话、摘要生成

职责：
- format_form_data — 将表单字典转为易读文本
- _build_lc_messages — 转换为 LangChain 消息格式（System + 历史 + 当前）
- _serialize_messages — 转回前端 {role, content} 格式
- ConversationService 类：
  - start_conversation_stream — AI 主动破冰问候（阶段1模板）
  - continue_conversation_stream — 接续对话（全部5阶段指令 + 历史）
  - generate_summary — 非流式需求摘要生成
"""

from datetime import datetime, timezone
from typing import AsyncGenerator

from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage

from core.state import ChatMessage, SessionData
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

    lines = [
        f"产品名称：{form.product_name}",
        f"一句话定义：{form.one_liner}",
        f"核心痛点：{form.problem_statement}",
        f"目标用户：{form.target_users}",
        f"MVP 功能清单：{', '.join(form.mvp_features)}",
        f"目标平台：{form.platform_type}",
        f"是否需要登录：{form.needs_auth}",
        f"是否需要数据库：{form.needs_database}",
        f"页面数量预估：{form.page_count}",
    ]
    # 选填字段（有值才输出）
    if form.visual_style:
        lines.append(f"视觉风格偏好：{form.visual_style}")
    if form.competitors:
        lines.append(f"竞品参考：{form.competitors}")
    if form.tech_stack_preference:
        lines.append(f"技术限制：{form.tech_stack_preference}")
    if form.feature_priority:
        lines.append(f"优先级策略：{form.feature_priority}")
    if form.doc_depth:
        lines.append(f"文档详细程度：{form.doc_depth}")
    if form.ai_temperature:
        lines.append(f"AI 输出风格：{form.ai_temperature}")
    if form.timeline_expectation:
        lines.append(f"时间预期：{form.timeline_expectation}")
    if form.additional_context:
        lines.append(f"额外上下文：{form.additional_context}")

    return "\n".join(lines)


def _render_stage(template_name: str, session: SessionData) -> str:
    """渲染单个阶段 Jinja2 模板，不传 chat_history（由 LangChain 消息链承载）"""
    form = session.form_data
    kwargs: dict = {}

    if form:
        kwargs.update(
            product_name=form.product_name,
            one_liner=form.one_liner,
            problem_statement=form.problem_statement,
            target_users=form.target_users,
            mvp_features=", ".join(form.mvp_features),
            platform_type=form.platform_type,
            needs_auth=form.needs_auth,
            needs_database=form.needs_database,
            page_count=form.page_count,
            visual_style=form.visual_style or "",
            competitors=form.competitors or "",
            tech_stack_preference=form.tech_stack_preference or "",
            timeline_expectation=form.timeline_expectation or "",
        )

    # 阶段专属参数
    if template_name == "stage_tech.jinja2":
        kwargs["mvp_feature_count"] = str(len(form.mvp_features)) if form else "0"
    elif template_name == "stage_summary.jinja2":
        kwargs["form_data_json"] = form.model_dump_json() if form else "{}"
        kwargs["full_chat_history"] = ""  # 由 LangChain 消息链承载
        # stage_summary 没有 chat_history 参数，不需要传

    # 需要 chat_history 的阶段（除 icebreak 外）
    if template_name not in ("stage_icebreak.jinja2", "stage_summary.jinja2"):
        kwargs["chat_history"] = ""  # 由 LangChain 消息链承载

    return load_prompt(f"backend/prompts/{template_name}", **kwargs)


def _build_system_prompt(session: SessionData, full: bool = False) -> str:
    """构建系统 Prompt。

    Args:
        session: 会话数据
        full: True = 包含全部 5 阶段指令（接续对话用）
              False = 仅阶段1 破冰指令（首次问候用）
    """
    if not full:
        return _render_stage("stage_icebreak.jinja2", session)

    # 拼接全部 5 阶段
    stage_names = [
        "stage_icebreak.jinja2",
        "stage_features.jinja2",
        "stage_competition.jinja2",
        "stage_tech.jinja2",
        "stage_summary.jinja2",
    ]
    stage_bodies = [_render_stage(n, session) for n in stage_names]

    form_text = format_form_data(session)
    header = (
        "你是一名资深产品经理顾问，有十年以上 B2B SaaS 产品经验。\n\n"
        "## 用户产品信息\n"
        f"{form_text}\n\n"
        "你将分 5 个阶段与用户对话。每个阶段的指令已在下文给出。\n"
        "请根据对话进展自主判断当前所处的阶段，并按对应阶段的指令行动。\n"
        "当前对话历史已在消息列表中提供，请勿重复询问已讨论过的内容。\n"
    )
    return header + "\n---\n" + "\n---\n".join(stage_bodies)


def _build_lc_messages(
    session: SessionData,
    user_message: str,
    full_system: bool = False,
) -> list[BaseMessage]:
    """构建 LangChain 消息列表：System + 历史 Human/AI + 当前 Human"""
    messages: list[BaseMessage] = [
        SystemMessage(content=_build_system_prompt(session, full=full_system)),
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
        使用阶段1（破冰 & 场景还原）模板，不含对话历史。

        Yields:
            逐 token 文本块。
        完成后自动将 AI 消息追加到 session.chat_messages 并回写存储。
        """
        if session.chat_messages:
            return  # 已有消息不重新开始

        system = _build_system_prompt(session, full=False)
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
        使用全部 5 阶段指令 + 完整对话历史。

        Args:
            session: 当前会话
            user_message: 用户刚发送的消息内容

        Yields:
            逐 token 文本块。
        完成后自动将 AI 消息追加到 session.chat_messages 并回写存储。
        """
        messages = _build_lc_messages(session, user_message, full_system=True)

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

        渲染 stage_summary.jinja2 模板并调用 LLM，
        结果写入 session.requirements_summary 并持久化。
        """
        summary_prompt = _render_stage("stage_summary.jinja2", session)

        result = await self._llm.ainvoke([
            SystemMessage(content=summary_prompt),
            HumanMessage(content="请根据以上对话生成需求摘要"),
        ])

        summary = result.content if hasattr(result, "content") else str(result)
        session.requirements_summary = summary
        update_session(session)
        return summary

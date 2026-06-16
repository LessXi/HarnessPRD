"""测试 conversation_service.py 的纯函数（无需 LLM）"""

import pytest
from langchain.schema import AIMessage, HumanMessage, SystemMessage

from services.conversation_service import (
    format_form_data,
    _build_system_prompt,
    _build_lc_messages,
    _serialize_messages,
)


class TestFormatFormData:
    """format_form_data — 表单字典转易读文本"""

    def test_with_form_data(self, mock_session):
        """有表单数据时输出包含产品名称等多行文本"""
        text = format_form_data(mock_session)
        assert "智能简历助手" in text
        assert "一键简历解析" in text
        assert "目标平台" in text
        assert "Zety" in text  # 选填字段
        assert "Python + React" in text
        assert "3-6_months" in text
        # 验证所有必填字段都有输出
        for keyword in ["产品名称", "一句话定义", "核心痛点", "目标用户", "MVP 功能清单"]:
            assert keyword in text, f"缺少关键字段: {keyword}"

    def test_without_form_data(self):
        """无表单数据时输出兜底文本"""
        from unittest.mock import MagicMock
        session = MagicMock()
        session.form_data = None
        text = format_form_data(session)
        assert "无表单数据" in text


class TestBuildSystemPrompt:
    """_build_system_prompt — 系统提示词构建"""

    def test_icebreak_only(self, mock_session):
        """full=False 时仅包含阶段1（破冰）"""
        prompt = _build_system_prompt(mock_session, full=False)
        assert isinstance(prompt, str)
        assert len(prompt) > 100
        # 应该包含 icebreak 阶段的角色定义
        assert "产品经理" in prompt
        # 不应包含后续阶段的标记
        assert "破冰" in prompt or "场景还原" in prompt

    def test_full_stages(self, mock_session):
        """full=True 时包含全部 5 阶段"""
        prompt = _build_system_prompt(mock_session, full=True)
        assert isinstance(prompt, str)
        assert len(prompt) > 500
        # 应该包含多阶段指令
        assert "阶段" in prompt
        # 包含完整的用户产品信息
        assert "智能简历助手" in prompt

    def test_full_system_contains_form_data(self, mock_session):
        """full 模式下包含格式化表单数据"""
        prompt = _build_system_prompt(mock_session, full=True)
        assert "智能简历助手" in prompt
        assert "一键简历解析" in prompt


class TestBuildLcMessages:
    """_build_lc_messages — LangChain 消息链构建"""

    def test_first_message(self, mock_session):
        """无历史消息时返回 [System, Human]"""
        messages = _build_lc_messages(mock_session, "你好", full_system=False)
        assert len(messages) == 2
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)
        assert messages[1].content == "你好"

    def test_with_history(self, mock_session_with_history):
        """有历史消息时返回 [System, AI, Human, AI, Human]（mock 首条为 AI 问候）"""
        msg = "我想先做 Web 端"
        messages = _build_lc_messages(mock_session_with_history, msg, full_system=True)
        # System + 3 chat_messages + 1 new = 5
        assert len(messages) == 5
        assert isinstance(messages[0], SystemMessage)
        # mock_session_with_history 的 chat_messages: [assistant, user, assistant]
        assert isinstance(messages[1], AIMessage)       # assistant 问候
        assert isinstance(messages[2], HumanMessage)    # user
        assert isinstance(messages[3], AIMessage)       # assistant
        assert isinstance(messages[4], HumanMessage)    # new message
        assert messages[4].content == msg

    def test_empty_user_message(self, mock_session):
        """空消息时不应添加 HumanMessage"""
        messages = _build_lc_messages(mock_session, "", full_system=False)
        assert len(messages) == 1
        assert isinstance(messages[0], SystemMessage)


class TestSerializeMessages:
    """_serialize_messages — 转前端 {role, content} 格式"""

    def test_skip_system(self):
        """SystemMessage 被跳过"""
        msgs = [
            SystemMessage(content="system prompt"),
            HumanMessage(content="hello"),
            AIMessage(content="hi there"),
        ]
        result = _serialize_messages(msgs)
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "hello"}
        assert result[1] == {"role": "assistant", "content": "hi there"}

    def test_ordering(self):
        """消息顺序不变"""
        msgs = [
            HumanMessage(content="a"),
            AIMessage(content="b"),
            HumanMessage(content="c"),
        ]
        result = _serialize_messages(msgs)
        assert [r["content"] for r in result] == ["a", "b", "c"]

    def test_empty(self):
        """空输入返回空列表"""
        assert _serialize_messages([]) == []

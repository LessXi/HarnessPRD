"""测试 conversation_service.py 的纯函数（无需 LLM）"""

import pytest
from langchain.schema import AIMessage, HumanMessage, SystemMessage

from core.state import FormData
from services.conversation_service import (
    _form_to_kwargs,
    _build_system_prompt,
    _build_lc_messages,
)


class TestFormToKwargs:
    """_form_to_kwargs — 表单字典转模板上下文"""

    def test_with_form_data(self, mock_form_data):
        """有表单数据时输出包含产品名称等字段"""
        kwargs = _form_to_kwargs(mock_form_data)
        assert kwargs["product_name"] == "智能简历助手"
        assert kwargs["mvp_features"] == "一键简历解析, 智能关键词匹配, 投递记录追踪, ATS 兼容性检查"
        assert kwargs["platform_type"] == "web"
        assert kwargs["competitors"] == "Zety"
        assert kwargs["tech_stack_preference"] == "Python + React"
        # form_fields 列表
        assert len(kwargs["form_fields"]) > 10

    def test_empty_form_data(self):
        """空表单返回默认值（required 字段仍出现在 form_fields 中）"""
        empty = FormData(
            product_name="",
            one_liner="",
            problem_statement="",
            target_users="",
            mvp_features=["", "", ""],
            platform_type="web",
            needs_auth="yes",
            needs_database="yes",
            page_count="1-3",
        )
        kwargs = _form_to_kwargs(empty)
        assert kwargs["product_name"] == ""
        # required 字段即使为空也出现在 form_fields 中
        assert len(kwargs["form_fields"]) > 0


class TestBuildSystemPrompt:
    """_build_system_prompt — 统一的系统提示词构建"""

    def test_contains_role_definition(self, mock_form_data):
        """提示词包含产品经理角色定义"""
        prompt = _build_system_prompt(mock_form_data)
        assert isinstance(prompt, str)
        assert len(prompt) > 200
        assert "产品经理" in prompt or "产品合伙人" in prompt

    def test_contains_form_data(self, mock_form_data):
        """提示词包含完整的表单数据"""
        prompt = _build_system_prompt(mock_form_data)
        assert "智能简历助手" in prompt
        assert "一键简历解析" in prompt

    def test_contains_topic_map(self, mock_form_data):
        """提示词包含 5 个话题方向"""
        prompt = _build_system_prompt(mock_form_data)
        assert "使用场景" in prompt
        assert "功能边界" in prompt or "核心功能" in prompt
        assert "行为原则" in prompt
        assert "倾听优先" in prompt

    def test_contains_skip_logic(self, mock_form_data):
        """提示词包含跳过对话的兜底逻辑"""
        prompt = _build_system_prompt(mock_form_data)
        assert "跳过" in prompt


class TestBuildLcMessages:
    """_build_lc_messages — LangChain 消息链构建"""

    def test_first_message(self, mock_form_data):
        """无历史消息时返回 [System, Human]"""
        system = _build_system_prompt(mock_form_data)
        messages = _build_lc_messages(system, [], "你好")
        assert len(messages) == 2
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)
        assert messages[1].content == "你好"

    def test_icebreaker(self, mock_form_data):
        """用户消息为空时返回 [System]（破冰场景）"""
        system = _build_system_prompt(mock_form_data)
        messages = _build_lc_messages(system, [], "")
        assert len(messages) == 1
        assert isinstance(messages[0], SystemMessage)

    def test_with_history(self, mock_form_data, mock_history):
        """有历史消息时返回 [System, AI, Human, AI, Human]"""
        system = _build_system_prompt(mock_form_data)
        msg = "我想先做 Web 端"
        messages = _build_lc_messages(system, mock_history, msg)
        # System + 3 history + 1 new = 5
        assert len(messages) == 5
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], AIMessage)       # assistant 问候
        assert isinstance(messages[2], HumanMessage)    # user
        assert isinstance(messages[3], AIMessage)       # assistant
        assert isinstance(messages[4], HumanMessage)    # new message
        assert messages[4].content == msg

    def test_with_history_no_new_message(self, mock_form_data, mock_history):
        """不带新消息时仅返回 [System] + 历史"""
        system = _build_system_prompt(mock_form_data)
        messages = _build_lc_messages(system, mock_history, "")
        assert len(messages) == 4  # System + 3 history
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], AIMessage)
        assert isinstance(messages[2], HumanMessage)
        assert isinstance(messages[3], AIMessage)

    def test_empty_input(self, mock_form_data):
        """全空输入返回 [System]"""
        system = _build_system_prompt(mock_form_data)
        messages = _build_lc_messages(system, [], "")
        assert len(messages) == 1
        assert isinstance(messages[0], SystemMessage)

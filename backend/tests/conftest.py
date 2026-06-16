"""测试共用的 mock 会话和 fixture"""

import pytest
from datetime import datetime, timezone

from core.state import ChatMessage, FormData, SessionData, session_store


@pytest.fixture
def mock_form_data() -> FormData:
    """返回一个填满必填字段的 mock 表单"""
    return FormData(
        product_name="智能简历助手",
        one_liner="AI 驱动的简历优化和投递管理工具",
        problem_statement="求职者花大量时间修改简历，但不知道什么内容对特定岗位有效",
        target_users="应届毕业生和 3-5 年经验的职场人士",
        mvp_features=["一键简历解析", "智能关键词匹配", "投递记录追踪", "ATS 兼容性检查"],
        platform_type="web",
        needs_auth="yes",
        needs_database="yes",
        page_count="4-10",
        visual_style="minimal",
        competitors="Zety",
        tech_stack_preference="Python + React",
        feature_priority="ai_suggest",
        timeline_expectation="3-6_months",
    )


@pytest.fixture
def mock_session(mock_form_data: FormData) -> SessionData:
    """返回创建好的 mock 会话（已进入 AI_DIALOGUE 状态）"""
    return session_store.create(mock_form_data)


@pytest.fixture
def mock_session_with_history(mock_form_data: FormData) -> SessionData:
    """返回带 2 轮对话历史的 mock 会话"""
    session = session_store.create(mock_form_data)
    session.chat_messages = [
        ChatMessage(role="assistant", content="你好！我是你的产品顾问，请说说你的想法。", timestamp=datetime.now(timezone.utc)),
        ChatMessage(role="user", content="我想做一个简历工具", timestamp=datetime.now(timezone.utc)),
        ChatMessage(role="assistant", content="好的，能具体说说你的目标用户是谁吗？", timestamp=datetime.now(timezone.utc)),
    ]
    session_store.update(session)
    return session


@pytest.fixture(autouse=True)
def _clean_store():
    """每个测试前清空 session_store"""
    session_store._sessions.clear()
    yield

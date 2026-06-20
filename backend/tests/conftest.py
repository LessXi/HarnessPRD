"""测试共用的 mock 数据和 fixture"""

import pytest
from datetime import datetime, timezone

from core.state import ChatMessage, FormData


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
def mock_form_dict(mock_form_data: FormData) -> dict:
    """返回表单数据的字典形式，供新无状态 API 使用"""
    return mock_form_data.model_dump()


@pytest.fixture
def mock_history() -> list[dict]:
    """返回带 2 轮对话历史的 mock 数据"""
    return [
        {"role": "assistant", "content": "你好！我是你的产品顾问，请说说你的想法。", "timestamp": datetime.now(timezone.utc).isoformat()},
        {"role": "user", "content": "我想做一个简历工具", "timestamp": datetime.now(timezone.utc).isoformat()},
        {"role": "assistant", "content": "好的，能具体说说你的目标用户是谁吗？", "timestamp": datetime.now(timezone.utc).isoformat()},
    ]

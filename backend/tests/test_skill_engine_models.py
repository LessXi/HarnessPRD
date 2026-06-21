"""测试 skill_engine 数据模型。"""

import pytest
from pydantic import ValidationError

from skill_engine.models import (
    SSEEvent,
    SkillNotFoundError,
    SkillParseError,
    SkillSchema,
    StepSchema,
)


class TestStepSchema:
    """StepSchema 创建和校验"""

    def test_create_generate_step(self):
        """正常创建 generate 类型步骤"""
        step = StepSchema(
            id="prd_generate",
            type="generate",
            prompt="写一份 PRD 文档",
        )
        assert step.id == "prd_generate"
        assert step.type == "generate"
        assert step.prompt == "写一份 PRD 文档"
        assert step.pass_condition is None

    def test_create_review_step(self):
        """正常创建 review 类型步骤，含 pass_condition"""
        step = StepSchema(
            id="prd_review",
            type="review",
            prompt="审阅 PRD 文档",
            pass_condition="所有章节完整",
        )
        assert step.id == "prd_review"
        assert step.type == "review"
        assert step.pass_condition == "所有章节完整"

    def test_create_rewrite_step(self):
        """正常创建 rewrite 类型步骤"""
        step = StepSchema(
            id="prd_rewrite",
            type="rewrite",
            prompt="根据审阅意见重写",
        )
        assert step.type == "rewrite"

    def test_invalid_type(self):
        """type 为非法字符串时抛出 ValidationError"""
        with pytest.raises(ValidationError):
            StepSchema(
                id="bad_step",
                type="translate",  # 不在 Literal 中
                prompt="翻译文档",
            )


class TestSkillSchema:
    """SkillSchema 创建和校验"""

    def test_create_minimal(self):
        """最少字段创建"""
        skill = SkillSchema(
            name="prd_generator",
            description="生成 PRD 文档",
            steps=[
                StepSchema(id="s1", type="generate", prompt="生成 PRD"),
            ],
        )
        assert skill.name == "prd_generator"
        assert skill.max_iterations == 3  # 默认值
        assert len(skill.steps) == 1

    def test_create_full(self):
        """全字段创建"""
        skill = SkillSchema(
            name="prd_generator",
            description="生成并优化 PRD 文档",
            max_iterations=5,
            steps=[
                StepSchema(id="s1", type="generate", prompt="生成 PRD"),
                StepSchema(
                    id="s2",
                    type="review",
                    prompt="审阅 PRD",
                    pass_condition="无缺失章节",
                ),
                StepSchema(id="s3", type="rewrite", prompt="根据意见重写"),
            ],
        )
        assert skill.max_iterations == 5
        assert len(skill.steps) == 3
        assert skill.steps[1].pass_condition == "无缺失章节"

    def test_invalid_max_iterations(self):
        """max_iterations 不能为负数（Pydantic 正整数约束）"""
        with pytest.raises(ValidationError):
            SkillSchema(
                name="bad",
                description="bad skill",
                max_iterations=-1,
                steps=[
                    StepSchema(id="s1", type="generate", prompt="test"),
                ],
            )

    def test_empty_steps(self):
        """steps 为空列表时抛出 ValidationError"""
        with pytest.raises(ValidationError):
            SkillSchema(
                name="empty",
                description="empty steps",
                steps=[],
            )


class TestSSEEvent:
    """SSEEvent 创建和序列化"""

    def test_create_chunk(self):
        """创建 chunk 事件"""
        event = SSEEvent(event="chunk", content="Hello")
        assert event.event == "chunk"
        assert event.content == "Hello"
        assert event.passed is None
        assert event.issues is None

    def test_create_done(self):
        """创建 done 事件（仅 event 必填）"""
        event = SSEEvent(event="done")
        assert event.event == "done"
        assert event.content == ""  # 默认值

    def test_create_review_result(self):
        """创建 review_result 事件"""
        event = SSEEvent(
            event="review_result",
            content="审阅通过",
            passed=True,
            issues=["格式问题"],
        )
        assert event.passed is True
        assert event.issues == ["格式问题"]

    def test_create_error(self):
        """创建 error 事件"""
        event = SSEEvent(event="error", content="出错了")
        assert event.event == "error"

    def test_invalid_event(self):
        """event 为非法值时抛出 ValidationError"""
        with pytest.raises(ValidationError):
            SSEEvent(event="unknown_event")

    def test_to_dict(self):
        """验证 dict 序列化"""
        event = SSEEvent(event="chunk", content="Hello")
        d = event.model_dump()
        assert d["event"] == "chunk"
        assert d["content"] == "Hello"
        assert d["passed"] is None
        assert d["issues"] is None

    def test_review_result_to_dict(self):
        """验证 review_result 完整序列化"""
        event = SSEEvent(
            event="review_result",
            content="需要修改",
            passed=False,
            issues=["问题1", "问题2"],
        )
        d = event.model_dump(exclude_none=False)
        # Pydantic v2: exclude_none=False 时 None 字段也保留
        assert d["event"] == "review_result"
        assert d["passed"] is False
        assert d["issues"] == ["问题1", "问题2"]


class TestSkillParseError:
    """SkillParseError 异常"""

    def test_raise_and_catch(self):
        """可抛出并捕获"""
        with pytest.raises(SkillParseError) as exc_info:
            raise SkillParseError("YAML 解析失败")
        assert "YAML 解析失败" in str(exc_info.value)

    def test_is_exception(self):
        """是 Exception 子类"""
        assert issubclass(SkillParseError, Exception)


class TestSkillNotFoundError:
    """SkillNotFoundError 异常"""

    def test_raise_and_catch(self):
        """可抛出并捕获"""
        with pytest.raises(SkillNotFoundError) as exc_info:
            raise SkillNotFoundError("skill 'xxx' 未找到")
        assert "xxx" in str(exc_info.value)

    def test_is_exception(self):
        """是 Exception 子类"""
        assert issubclass(SkillNotFoundError, Exception)

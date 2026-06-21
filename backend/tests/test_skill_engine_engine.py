"""测试 SkillEngine 执行器 — generate→review→rewrite 循环。

RED: engine.py 尚不存在，此测试应 ImportError。
GREEN: 实现 engine.py 后全部通过。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain.schema import AIMessage

from skill_engine.models import SSEEvent, SkillSchema, StepSchema


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_llm_service():
    """可配置的 mock LLM service 工厂 fixture。

    返回一个 builder 函数，各测试调用时指定:
        review_response: ``_call_llm_once`` 返回的文本
        stream_tokens: ``stream_generate`` 依次 yield 的 token 列表
    """

    def _build(
        review_response: str = '{"passed": true, "issues": []}',
        stream_tokens: list[str] | None = None,
    ):
        service = MagicMock()
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content=review_response)
        )
        service.get_llm.return_value = mock_llm

        if stream_tokens is None:
            stream_tokens = ["mock content"]

        async def _stream(prompt: str, **kwargs):
            for token in stream_tokens:
                yield token

        service.stream_generate = _stream
        return service

    return _build


# ============================================================
# _parse_review_result 单元测试
# ============================================================


class TestParseReviewResult:
    """_parse_review_result — JSON 优先，关键词降级"""

    def test_json_passed(self):
        """JSON 解析：passed=true + issues 列表"""
        engine = self._make_engine()
        passed, issues = engine._parse_review_result(
            '{"passed": true, "issues": []}',
            "通过",
        )
        assert passed is True
        assert issues == []

    def test_json_failed_with_issues(self):
        """JSON 解析：passed=false + issues 有内容"""
        engine = self._make_engine()
        passed, issues = engine._parse_review_result(
            '{"passed": false, "issues": ["缺少细节", "格式错误"]}',
            "通过",
        )
        assert passed is False
        assert issues == ["缺少细节", "格式错误"]

    def test_json_no_issues_key(self):
        """JSON 解析：缺 issues 键 → issues 兜底为空列表"""
        engine = self._make_engine()
        passed, issues = engine._parse_review_result(
            '{"passed": true}',
            "通过",
        )
        assert passed is True
        assert issues == []

    def test_json_issues_not_list(self):
        """JSON 解析：issues 不是列表 → 兜底为空列表"""
        engine = self._make_engine()
        passed, issues = engine._parse_review_result(
            '{"passed": false, "issues": "单个字符串"}',
            "通过",
        )
        assert passed is False
        assert issues == []

    def test_keyword_passed(self):
        """JSON 解析失败 → 关键词匹配：命中 pass_condition"""
        engine = self._make_engine()
        passed, issues = engine._parse_review_result(
            "审核通过\n文档内容完整",
            "审核通过",
        )
        assert passed is True
        assert issues == []

    def test_keyword_failed(self):
        """JSON 解析失败 → 关键词匹配：未命中 pass_condition"""
        engine = self._make_engine()
        passed, issues = engine._parse_review_result(
            "审核不通过\n需要补充细节",
            "审核通过",
        )
        assert passed is False
        assert issues == []

    def test_keyword_empty_text(self):
        """空文本 + 有 pass_condition → 不通过"""
        engine = self._make_engine()
        passed, issues = engine._parse_review_result("", "审核通过")
        assert passed is False
        assert issues == []

    def test_no_pass_condition(self):
        """pass_condition=None → 自动通过"""
        engine = self._make_engine()
        passed, issues = engine._parse_review_result("任意内容", None)
        assert passed is True
        assert issues == []

    # --------------------------------------------------
    # helpers
    # --------------------------------------------------

    @staticmethod
    def _make_engine():
        from skill_engine.engine import SkillEngine

        return SkillEngine(MagicMock())


# ============================================================
# execute 主循环 — 流式事件序列
# ============================================================


class TestSkillEngineExecute:
    """SkillEngine.execute — generate→review→rewrite 循环"""

    # --------------------------------------------------
    # 基础场景
    # --------------------------------------------------

    @pytest.mark.asyncio
    async def test_generate_only(self, mock_llm_service):
        """单 generate 步骤 → yield chunk×N → done"""
        service = mock_llm_service(stream_tokens=["Hello", " ", "World"])
        engine = self._make_engine(service)
        skill = SkillSchema(
            name="test",
            description="test",
            max_iterations=1,
            steps=[StepSchema(id="gen", type="generate", prompt="生成内容")],
        )
        events = [e async for e in engine.execute(skill, {})]

        assert len(events) == 4  # 3 chunk + 1 done
        assert events[0].event == "chunk"
        assert events[0].content == "Hello"
        assert events[1].content == " "
        assert events[2].content == "World"
        assert events[3].event == "done"
        assert events[3].content == "Hello World"

    @pytest.mark.asyncio
    async def test_generate_review_pass(self, mock_llm_service):
        """generate + review 通过 → 立即 done，无 rewrite"""
        service = mock_llm_service(
            review_response='{"passed": true, "issues": []}',
            stream_tokens=["doc content"],
        )
        engine = self._make_engine(service)
        skill = SkillSchema(
            name="test",
            description="test",
            steps=[
                StepSchema(id="gen", type="generate", prompt="生成"),
                StepSchema(
                    id="review",
                    type="review",
                    prompt="审阅",
                    pass_condition="通过",
                ),
            ],
        )
        events = [e async for e in engine.execute(skill, {})]

        # gen(1 chunk) + review(1 chunk + 1 review_result) + done
        assert len(events) == 4
        assert events[0].event == "chunk"  # generate token
        assert events[0].content == "doc content"
        assert events[1].event == "chunk"  # review full text
        assert events[2].event == "review_result"
        assert events[2].passed is True
        assert events[2].issues == []
        assert events[3].event == "done"

    @pytest.mark.asyncio
    async def test_generate_review_fail_rewrite_review_pass(
        self, mock_llm_service
    ):
        """generate → review 不通过 → rewrite → review 通过 → done"""
        call_count = [0]

        async def ainvoke_side_effect(messages):
            call_count[0] += 1
            if call_count[0] == 1:
                return AIMessage(
                    content='{"passed": false, "issues": ["缺细节"]}'
                )
            return AIMessage(content='{"passed": true, "issues": []}')

        service = MagicMock()
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=ainvoke_side_effect)
        service.get_llm.return_value = mock_llm

        async def _stream(prompt, **kwargs):
            yield "rewritten content"

        service.stream_generate = _stream

        engine = self._make_engine(service)
        skill = SkillSchema(
            name="test",
            description="test",
            max_iterations=3,
            steps=[
                StepSchema(id="gen", type="generate", prompt="生成"),
                StepSchema(
                    id="review",
                    type="review",
                    prompt="审阅",
                    pass_condition="通过",
                ),
                StepSchema(id="rewrite", type="rewrite", prompt="重写"),
                StepSchema(
                    id="review2",
                    type="review",
                    prompt="再审阅",
                    pass_condition="通过",
                ),
            ],
        )
        events = [e async for e in engine.execute(skill, {})]

        # gen(1) + review1(1chunk+1result) + rewrite(1) + review2(1chunk+1result+1done)
        assert len(events) == 7

        # Review 1: 不通过
        assert events[2].event == "review_result"
        assert events[2].passed is False
        assert events[2].issues == ["缺细节"]

        # Review 2: 通过 + done
        assert events[5].event == "review_result"
        assert events[5].passed is True
        assert events[6].event == "done"

    # --------------------------------------------------
    # 边界条件
    # --------------------------------------------------

    @pytest.mark.asyncio
    async def test_max_iterations_exhausted(self, mock_llm_service):
        """review 持续不通过 → 达到 max_iterations 后强制 done"""
        service = mock_llm_service(
            review_response='{"passed": false, "issues": ["总是有问题"]}',
            stream_tokens=["content"],
        )
        engine = self._make_engine(service)
        skill = SkillSchema(
            name="test",
            description="test",
            max_iterations=2,
            steps=[
                StepSchema(id="gen", type="generate", prompt="生成"),
                StepSchema(
                    id="review",
                    type="review",
                    prompt="审阅",
                    pass_condition="通过",
                ),
            ],
        )
        events = [e async for e in engine.execute(skill, {})]

        # round0: gen(1chunk) + review(1chunk+1result_失败)
        # round1: gen(1chunk) + review(1chunk+1result_失败)
        # done
        assert len(events) == 7

        # 两次 review 都失败
        assert events[2].event == "review_result"
        assert events[2].passed is False
        assert events[5].event == "review_result"
        assert events[5].passed is False

        # 最后强制 done
        assert events[6].event == "done"

    @pytest.mark.asyncio
    async def test_event_count_with_multi_step(self, mock_llm_service):
        """事件计数 = gen token + review chunk + rewrite token + review_result + done"""
        service = mock_llm_service(
            review_response='{"passed": false, "issues": ["问题"]}',
            stream_tokens=["part1", "part2"],
        )
        engine = self._make_engine(service)
        skill = SkillSchema(
            name="test",
            description="test",
            max_iterations=1,
            steps=[
                StepSchema(id="gen", type="generate", prompt="生成"),
                StepSchema(
                    id="review",
                    type="review",
                    prompt="审阅",
                    pass_condition="通过",
                ),
                StepSchema(id="rewrite", type="rewrite", prompt="重写"),
                StepSchema(
                    id="review2",
                    type="review",
                    prompt="再审阅",
                    pass_condition="通过",
                ),
            ],
        )
        events = [e async for e in engine.execute(skill, {})]

        # gen(2) + review(1chunk+1result) + rewrite(2) + review(1chunk+1result) + done
        assert len(events) == 9
        assert events[-1].event == "done"

    @pytest.mark.asyncio
    async def test_empty_context(self, mock_llm_service):
        """空 context dict 不引发异常"""
        service = mock_llm_service(stream_tokens=["hello"])
        engine = self._make_engine(service)
        skill = SkillSchema(
            name="test",
            description="test",
            max_iterations=1,
            steps=[StepSchema(id="gen", type="generate", prompt="生成")],
        )
        events = [e async for e in engine.execute(skill, {})]
        assert len(events) == 2  # 1 chunk + 1 done
        assert events[1].event == "done"

    @pytest.mark.asyncio
    async def test_review_no_pass_condition(self, mock_llm_service):
        """review 步骤无 pass_condition → 自动通过，直接 done"""
        service = mock_llm_service(
            review_response="随便什么内容",
            stream_tokens=["doc"],
        )
        engine = self._make_engine(service)
        skill = SkillSchema(
            name="test",
            description="test",
            steps=[
                StepSchema(id="gen", type="generate", prompt="生成"),
                StepSchema(
                    id="review", type="review", prompt="审阅"
                ),  # no pass_condition
            ],
        )
        events = [e async for e in engine.execute(skill, {})]

        assert events[2].event == "review_result"
        assert events[2].passed is True
        assert events[3].event == "done"

    # --------------------------------------------------
    # helpers
    # --------------------------------------------------

    @staticmethod
    def _make_engine(llm_service):
        from skill_engine.engine import SkillEngine

        return SkillEngine(llm_service)

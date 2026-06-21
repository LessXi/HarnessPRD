"""Skill Engine 集成测试：三种文档类型完整生成流程 + SSE 格式验证 + 热加载

测试范围：
  1. generate_document_stream 对 prd/api/prompts 三种类型
  2. optimize_document_stream 跳过 generate 步骤
  3. review 不通过 → rewrite → review 通过 完整循环
  4. SSEEvent 序列化格式（chunk/done/review_result/error）
  5. 热加载 smoke test
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from langchain.schema import AIMessage

from skill_engine.models import SSEEvent


# ============================================================
# 最小 skill 定义（含 generate → review → rewrite 三步骤）
# ============================================================

_SKILL_PRD = """\
---
name: prd-generate
description: PRD 生成测试 skill
max_iterations: 3
steps:
  - id: generate
    type: generate
    prompt: |
      生成 {{ form_data.product_name }} 的 PRD
      需求摘要: {{ requirements_summary }}
  - id: review
    type: review
    prompt: |
      审阅: {{ current_content }}
    pass_condition: "审核通过"
  - id: rewrite
    type: rewrite
    prompt: |
      重写:
      {{ current_content }}
      意见: {{ review_result }}
      base: {{ base_prompt }}
---
"""

_SKILL_API = """\
---
name: api-generate
description: API 文档生成测试 skill
max_iterations: 3
steps:
  - id: generate
    type: generate
    prompt: |
      生成 {{ form_data.product_name }} 的 API 文档
      PRD: {{ prd_content }}
      摘要: {{ requirements_summary }}
  - id: review
    type: review
    prompt: |
      审阅: {{ current_content }}
    pass_condition: "审核通过"
  - id: rewrite
    type: rewrite
    prompt: |
      重写:
      {{ current_content }}
      意见: {{ review_result }}
---
"""

_SKILL_PROMPTS = """\
---
name: prompts-generate
description: 提示词套件生成测试 skill
max_iterations: 3
steps:
  - id: generate
    type: generate
    prompt: |
      生成 {{ form_data.product_name }} 的提示词套件
      PRD: {{ prd_content }}
      API: {{ api_content }}
      摘要: {{ requirements_summary }}
  - id: review
    type: review
    prompt: |
      审阅: {{ current_content }}
    pass_condition: "审核通过"
  - id: rewrite
    type: rewrite
    prompt: |
      重写:
      {{ current_content }}
      意见: {{ review_result }}
---
"""


# ============================================================
# 辅助函数
# ============================================================


def _write_skills(tmp_path: Path) -> None:
    """在 tmp_path/skills 下创建三个 skill 文件"""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(exist_ok=True)
    (skills_dir / "prd-generate.md").write_text(_SKILL_PRD, encoding="utf-8")
    (skills_dir / "api-generate.md").write_text(_SKILL_API, encoding="utf-8")
    (skills_dir / "prompts-generate.md").write_text(_SKILL_PROMPTS, encoding="utf-8")


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def skill_env(tmp_path: Path):
    """创建临时 skills 目录，初始化全局 SkillEngine

    每个测试函数独立 tmp_path，避免状态污染。
    无论 setup 成功与否，teardown 都清理全局变量。
    """
    from services.document_service import init_skill_engine

    # 确保之前的全局状态已清理
    import services.document_service as ds
    ds._skill_loader = None
    ds._skill_engine = None

    _write_skills(tmp_path)
    init_skill_engine(str(tmp_path / "skills"))

    yield

    ds._skill_loader = None
    ds._skill_engine = None


@pytest.fixture
def mock_llm_pass():
    """Mock LLM: stream_generate 返回固定 token, ainvoke 返回通过

    ``stream_generate`` 总是 yield ["mock", " ", "content"]
    ``get_llm().ainvoke`` 总是返回 ``{"passed": true, "issues": []}``
    """

    async def _stream(prompt: str, **kwargs):
        for token in ["mock", " ", "content"]:
            yield token

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content='{"passed": true, "issues": []}')
    )

    with patch("services.llm_service.stream_generate", _stream):
        with patch("services.llm_service.get_llm", return_value=mock_llm):
            yield


@pytest.fixture
def mock_llm_fail_then_pass():
    """Mock LLM: 第一次 review 不通过，第二次通过

    ``stream_generate`` 总是 yield ["rewritten", " ", "content"]
    ``get_llm().ainvoke``:
      - 第 1 次调用返回 ``{"passed": false, "issues": ["缺细节"]}``
      - 此后返回 ``{"passed": true, "issues": []}``
    """
    call_count = [0]

    async def _stream(prompt: str, **kwargs):
        for token in ["rewritten", " ", "content"]:
            yield token

    mock_llm = AsyncMock()

    async def _ainvoke(messages, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return AIMessage(content='{"passed": false, "issues": ["缺细节"]}')
        return AIMessage(content='{"passed": true, "issues": []}')

    mock_llm.ainvoke = AsyncMock(side_effect=_ainvoke)

    with patch("services.llm_service.stream_generate", _stream):
        with patch("services.llm_service.get_llm", return_value=mock_llm):
            yield


# ============================================================
# 集成测试 — 文档流式生成
# ============================================================


class TestGenerateStream:
    """三种文档类型的完整生成流程"""

    @pytest.mark.asyncio
    async def test_prd_generate_stream(
        self, skill_env, mock_llm_pass, mock_form_dict,
    ):
        """PRD 生成：chunk×3 → review_result(pass) → done"""
        from services.document_service import generate_document_stream

        events: list[SSEEvent] = []
        async for e in generate_document_stream(
            doc_type="prd",
            form_data=mock_form_dict,
            requirements_summary="测试需求摘要",
        ):
            events.append(e)

        # 3 chunk + 1 review_result + 1 done = 5
        assert len(events) == 5, f"预期 5 个事件, 实际 {len(events)}"

        assert events[0].event == "chunk"
        assert events[0].content == "mock"
        assert events[1].event == "chunk"
        assert events[1].content == " "
        assert events[2].event == "chunk"
        assert events[2].content == "content"

        assert events[3].event == "review_result"
        assert events[3].passed is True
        assert events[3].issues == []

        assert events[4].event == "done"
        assert events[4].content == "mock content"

    @pytest.mark.asyncio
    async def test_api_generate_stream(
        self, skill_env, mock_llm_pass, mock_form_dict,
    ):
        """API 文档生成：含 prd_content 上下文"""
        from services.document_service import generate_document_stream

        events: list[SSEEvent] = []
        async for e in generate_document_stream(
            doc_type="api",
            form_data=mock_form_dict,
            requirements_summary="测试需求摘要",
            prd_content="# PRD 内容",
        ):
            events.append(e)

        assert len(events) == 5
        assert events[-1].event == "done"
        assert events[-1].content == "mock content"

        review = events[3]
        assert review.event == "review_result"
        assert review.passed is True
        assert isinstance(review.issues, list)

    @pytest.mark.asyncio
    async def test_prompts_generate_stream(
        self, skill_env, mock_llm_pass, mock_form_dict,
    ):
        """提示词套件生成：含 prd_content + api_content 上下文"""
        from services.document_service import generate_document_stream

        events: list[SSEEvent] = []
        async for e in generate_document_stream(
            doc_type="prompts",
            form_data=mock_form_dict,
            requirements_summary="测试需求摘要",
            prd_content="# PRD 内容",
            api_content="# API 内容",
        ):
            events.append(e)

        assert len(events) == 5
        assert events[-1].event == "done"
        assert events[-1].content == "mock content"


class TestOptimizeStream:
    """文档优化 — review→rewrite 循环"""

    @pytest.mark.asyncio
    async def test_optimize_skips_generate(
        self, skill_env, mock_llm_pass, mock_form_dict,
    ):
        """优化流程：跳过 generate，直接 review → done"""
        from services.document_service import optimize_document_stream

        events: list[SSEEvent] = []
        async for e in optimize_document_stream(
            doc_type="prd",
            content="# 已有 PRD 内容",
            form_data=mock_form_dict,
            requirements_summary="测试需求摘要",
        ):
            events.append(e)

        # review_result + done = 2 (generate 被跳过)
        assert len(events) == 2, f"预期 2 个事件, 实际 {len(events)}"
        assert events[0].event == "review_result"
        assert events[0].passed is True
        assert events[1].event == "done"
        # current_content 直接取输入值（generate 未执行）
        assert events[1].content == "# 已有 PRD 内容"


class TestReviewFailRound:
    """审阅不通过 → rewrite → 再次审阅"""

    @pytest.mark.asyncio
    async def test_review_fail_then_rewrite_and_pass(
        self, skill_env, mock_llm_fail_then_pass, mock_form_dict,
    ):
        """generate → review(fail) → rewrite → review(pass) → done"""
        from services.document_service import generate_document_stream

        events: list[SSEEvent] = []
        async for e in generate_document_stream(
            doc_type="prd",
            form_data=mock_form_dict,
            requirements_summary="测试需求摘要",
        ):
            events.append(e)

        # round0: gen(3chunk) + review_fail(1) + rewrite(3chunk) = 7
        # round1: gen(3chunk) + review_pass(1) + done(1) = 5
        # total = 12
        assert len(events) == 12, f"预期 12 个事件, 实际 {len(events)}"

        # --- round 0 ---
        assert events[0].event == "chunk"
        assert events[3].event == "review_result"
        assert events[3].passed is False
        assert events[3].issues == ["缺细节"]

        # --- round 1 ---
        assert events[-2].event == "review_result"
        assert events[-2].passed is True
        assert events[-2].issues == []

        assert events[-1].event == "done"
        assert len(events[-1].content) > 0


# ============================================================
# SSE 事件格式验证
# ============================================================


class TestSSEEventFormat:
    """SSEEvent 序列化格式与前端 readStream 兼容"""

    def test_chunk_serialization(self):
        """chunk: {"event":"chunk","content":"..."}"""
        from api.sse_utils import serialize_sse_event

        event = SSEEvent(event="chunk", content="hello")
        output = serialize_sse_event(event)
        parsed = json.loads(output.split("\n")[0][6:])
        assert parsed["event"] == "chunk"
        assert parsed["content"] == "hello"
        assert output.endswith("\n\n")

    def test_done_serialization(self):
        """done: {"event":"done","content":"<全文>"}"""
        from api.sse_utils import serialize_sse_event

        event = SSEEvent(event="done", content="# Final doc")
        output = serialize_sse_event(event)
        parsed = json.loads(output.split("\n")[0][6:])
        assert parsed["event"] == "done"
        assert parsed["content"] == "# Final doc"

    def test_review_result_serialization(self):
        """review_result: 含 passed/issues/content"""
        from api.sse_utils import serialize_sse_event

        event = SSEEvent(
            event="review_result",
            content="问题: 缺细节",
            passed=False,
            issues=["缺细节"],
        )
        output = serialize_sse_event(event)
        parsed = json.loads(output.split("\n")[0][6:])
        assert parsed["event"] == "review_result"
        assert parsed["passed"] is False
        assert parsed["issues"] == ["缺细节"]
        assert parsed["content"] == "问题: 缺细节"

    def test_error_serialization(self):
        """error: {"event":"error","content":"..."}"""
        from api.sse_utils import serialize_sse_event

        event = SSEEvent(event="error", content="LLM 调用超时")
        output = serialize_sse_event(event)
        parsed = json.loads(output.split("\n")[0][6:])
        assert parsed["event"] == "error"
        assert parsed["content"] == "LLM 调用超时"


# ============================================================
# 热加载 smoke test
# ============================================================


class TestHotReload:
    """SkillLoader 热加载——运行时修改 skill 文件后 reload 生效"""

    def test_hot_reload_updates_skill(self, skill_env, tmp_path):
        """修改 skill 文件 → reload() → 最新内容生效"""
        from services.document_service import _skill_loader

        # 验证原始内容
        skill = _skill_loader.get("prd-generate")
        assert skill.description == "PRD 生成测试 skill"

        # 修改 skill 文件
        modified = _SKILL_PRD.replace(
            "PRD 生成测试 skill", "PRD 生成测试 v2"
        )
        (tmp_path / "skills" / "prd-generate.md").write_text(
            modified, encoding="utf-8"
        )

        # 热加载
        _skill_loader.reload()

        # 验证修改生效
        updated = _skill_loader.get("prd-generate")
        assert updated.description == "PRD 生成测试 v2"
        assert updated is not skill  # 新对象，非原地修改

    def test_hot_reload_preserves_other_skills(self, skill_env):
        """热加载不丢失其他已加载的 skill"""
        from services.document_service import _skill_loader

        names = _skill_loader.list_skills()
        assert "api-generate" in names
        assert "prompts-generate" in names
        assert len(names) == 3

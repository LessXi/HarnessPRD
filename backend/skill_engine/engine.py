"""Skill Engine 执行器：按 skill 步骤序列执行 generate→review→rewrite 循环。

提供 :class:`SkillEngine`，注入 LLM 服务模块后调用 :meth:`execute` 消费
:class:`~skill_engine.models.SkillSchema`，流式 yield |SSEEvent|。

典型用法::

    from skill_engine.engine import SkillEngine
    from skill_engine.parser import parse_skill_file

    engine = SkillEngine(llm_service)
    skill = parse_skill_file("skills/prd-generate.md")
    async for event in engine.execute(skill, {"form_data": {...}}):
        print(event.event, event.content)
"""

import json
import logging
import re
from typing import Any, AsyncGenerator, Protocol

from skill_engine.models import SSEEvent, SkillSchema
from skill_engine.parser import render_skill_prompt

logger = logging.getLogger(__name__)


class LLMServiceProtocol(Protocol):
    """LLM 服务协议：定义 SkillEngine 对 LLM 服务的期望接口。"""

    def stream_generate(self, prompt: str, **kwargs: Any) -> AsyncGenerator[str, None]:
        """流式调用 LLM，逐 token 生成。"""
        ...

    def get_llm(self) -> Any:
        """获取底层 LLM 实例（需具备 ainvoke 方法）。"""
        ...


class SkillEngine:
    """Skill 执行引擎。

    主入口 :meth:`execute` 遍历 skill 步骤，依次执行生成、审阅、改写，
    通过 ``AsyncGenerator[SSEEvent]`` 流式推送事件。
    """

    def __init__(self, llm_service: LLMServiceProtocol) -> None:
        """初始化引擎。

        Args:
            llm_service: LLM 服务模块（或足够兼容的 mock）。
                需要提供:
                - ``stream_generate(prompt, **kwargs)`` →
                  ``AsyncGenerator[str, None]``
                - ``get_llm()`` → 具备 ``ainvoke(messages)`` 方法的实例
        """
        self._llm = llm_service

    # ------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------

    async def execute(
        self,
        skill: SkillSchema,
        context: dict,
    ) -> AsyncGenerator[SSEEvent, None]:
        """执行 skill 主循环。

        主循环遍历 ``skill.steps``，每轮注入运行时上下文（``current_content``、
        ``review_result``、``base_prompt``、``iteration``）后渲染提示词，
        按 step type 分发：

        - ``generate`` / ``rewrite``: 调用 ``stream_generate`` 流式 yield chunk
        - ``review``: 调用 ``_call_llm_once`` 非流式获取审阅文本，
          解析并通过 ``review_result`` 事件返回结果；
          通过则 yield ``done`` 并返回，不通过将完整文本存入 ``review_result``
          供下一 rewrite 步骤使用

        支持从 ``context["current_content"]`` 传入已有内容。
        若已提供现有内容，自动跳过 generate 步骤（用于 optimize 场景）。
        generate 步骤渲染后的 prompt 自动保存为 ``base_prompt``，
        供 rewrite 步骤中的 ``{{ base_prompt }}`` 模板变量引用。

        Args:
            skill: 待执行的 skill 定义。
            context: 模板变量字典（含 form_data、requirements_summary 等）。

        Yields:
            SSEEvent: ``chunk`` / ``review_result`` / ``done`` 事件。
        """
        current_content = context.get("current_content", "")
        review_result = ""
        base_prompt = ""
        # 单次标记：仅在首轮首步时跳过 generate（optimize 场景从外部传入内容）
        _skip_first_generate = bool(current_content)

        for round_num in range(skill.max_iterations):
            for step in skill.steps:
                step_context: dict[str, Any] = {
                    **context,
                    "current_content": current_content,
                    "review_result": review_result,
                    "base_prompt": base_prompt,
                    "iteration": round_num,
                }
                prompt = render_skill_prompt(step, step_context)

                if step.type == "generate":
                    if _skip_first_generate:
                        _skip_first_generate = False
                        continue
                    current_content = ""
                    base_prompt = prompt
                    try:
                        async for token in self._llm.stream_generate(prompt):
                            yield SSEEvent(event="chunk", content=token)
                            current_content += token
                    except Exception as e:
                        yield SSEEvent(
                            event="error",
                            content=f"LLM 调用失败: {e}",
                        )
                        return

                elif step.type == "review":
                    try:
                        full = await self._call_llm_once(prompt)
                    except Exception as e:
                        yield SSEEvent(
                            event="error",
                            content=f"LLM 调用失败: {e}",
                        )
                        return
                    yield SSEEvent(event="chunk", content=full)
                    passed, issues = self._parse_review_result(
                        full, step.pass_condition
                    )
                    yield SSEEvent(
                        event="review_result",
                        content=full,
                        passed=passed,
                        issues=issues,
                    )
                    if passed:
                        yield SSEEvent(
                            event="done", content=current_content
                        )
                        return
                    review_result = full

                elif step.type == "rewrite":
                    current_content = ""
                    try:
                        async for token in self._llm.stream_generate(prompt):
                            yield SSEEvent(event="chunk", content=token)
                            current_content += token
                    except Exception as e:
                        yield SSEEvent(
                            event="error",
                            content=f"LLM 调用失败: {e}",
                        )
                        return

        # 达到 max_iterations 后强制结束
        yield SSEEvent(event="done", content=current_content)

    # ------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------

    @staticmethod
    def _parse_review_result(
        text: str,
        pass_condition: str | None,
    ) -> tuple[bool, list[str]]:
        """解析审阅结果。

        **策略**：
        1. ``pass_condition`` 为 ``None`` → 自动通过
        2. 尝试从 markdown 代码块 `` ```json ... ``` `` 中提取 JSON
        3. 回退到直接 ``json.loads(text)`` 解析
        4. 全部失败 → ``pass_condition in text`` 关键词匹配

        Args:
            text: LLM 返回的完整审阅文本。
            pass_condition: 通过条件字符串；``None`` 表示自动通过。

        Returns:
            ``(passed, issues)`` 二元组。
        """
        if pass_condition is None:
            return True, []

        # --- JSON 优先 ---

        def _try_parse(data_dict: dict) -> tuple[bool, list[str]] | None:
            """尝试从字典中提取 passed/issues。"""
            if "passed" in data_dict:
                passed = bool(data_dict["passed"])
                issues = data_dict.get("issues", [])
                if not isinstance(issues, list):
                    issues = []
                return passed, issues
            return None

        # 策略 1: 提取 markdown 代码块中的 JSON
        json_match = re.search(
            r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```", text, re.DOTALL
        )
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict):
                    result = _try_parse(data)
                    if result is not None:
                        return result
            except (json.JSONDecodeError, ValueError):
                pass

        # 策略 2: 直接解析全文（纯 JSON 输入）
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                result = _try_parse(data)
                if result is not None:
                    return result
        except (json.JSONDecodeError, ValueError):
            pass

        # --- 关键词降级 ---
        passed = pass_condition in text
        return passed, []

    async def _call_llm_once(self, prompt: str) -> str:
        """非流式调用 LLM。

        使用 ``get_llm().ainvoke()`` 获取完整响应文本。

        Args:
            prompt: 已渲染的完整提示词。

        Returns:
            响应文本（``response.content``）。
        """
        from langchain.schema import SystemMessage

        llm = self._llm.get_llm()
        response = await llm.ainvoke([SystemMessage(content=prompt)])
        if hasattr(response, "content"):
            return response.content
        if hasattr(response, "text"):
            return response.text
        logger.warning(
            "LLM response has no content/text attribute: %s", type(response)
        )
        return str(response)

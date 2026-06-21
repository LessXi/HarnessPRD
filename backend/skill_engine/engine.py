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
from typing import Any, AsyncGenerator

from skill_engine.models import SSEEvent, SkillSchema
from skill_engine.parser import render_skill_prompt


class SkillEngine:
    """Skill 执行引擎。

    主入口 :meth:`execute` 遍历 skill 步骤，依次执行生成、审阅、改写，
    通过 ``AsyncGenerator[SSEEvent]`` 流式推送事件。
    """

    def __init__(self, llm_service: Any) -> None:
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
        ``review_result``、``iteration``）后渲染提示词，按 step type 分发：

        - ``generate`` / ``rewrite``: 调用 ``stream_generate`` 流式 yield chunk
        - ``review``: 调用 ``_call_llm_once`` 非流式获取审阅文本，
          解析并通过 ``review_result`` 事件返回结果；
          通过则 yield ``done`` 并返回，不通过将完整文本存入 ``review_result``
          供下一 rewrite 步骤使用

        Args:
            skill: 待执行的 skill 定义。
            context: 模板变量字典（含 form_data、requirements_summary 等）。

        Yields:
            SSEEvent: ``chunk`` / ``review_result`` / ``done`` 事件。
        """
        current_content = ""
        review_result = ""

        for round_num in range(skill.max_iterations):
            for step in skill.steps:
                step_context: dict[str, Any] = {
                    **context,
                    "current_content": current_content,
                    "review_result": review_result,
                    "iteration": round_num,
                }
                prompt = render_skill_prompt(step, step_context)

                if step.type == "generate":
                    current_content = ""
                    async for token in self._llm.stream_generate(prompt):
                        yield SSEEvent(event="chunk", content=token)
                        current_content += token

                elif step.type == "review":
                    full = await self._call_llm_once(prompt)
                    yield SSEEvent(event="chunk", content=full)
                    passed, issues = self._parse_review_result(
                        full, step.pass_condition
                    )
                    yield SSEEvent(
                        event="review_result",
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
                    async for token in self._llm.stream_generate(prompt):
                        yield SSEEvent(event="chunk", content=token)
                        current_content += token

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
        2. 尝试 ``json.loads(text)`` 提取 ``{"passed": bool, "issues": [...]}``
        3. JSON 解析失败 → ``pass_condition in text`` 关键词匹配

        Args:
            text: LLM 返回的完整审阅文本。
            pass_condition: 通过条件字符串；``None`` 表示自动通过。

        Returns:
            ``(passed, issues)`` 二元组。
        """
        if pass_condition is None:
            return True, []

        # --- JSON 优先 ---
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "passed" in data:
                passed = bool(data["passed"])
                issues = data.get("issues", [])
                if not isinstance(issues, list):
                    issues = []
                return passed, issues
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
        return str(response)

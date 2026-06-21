"""Skill Engine 核心 Pydantic 数据模型。"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class StepSchema(BaseModel):
    """定义 skill 中的一个步骤。

    Attributes:
        id: 步骤唯一标识。
        type: 步骤类型 — generate（生成）、review（审阅）、rewrite（改写）。
        prompt: 步骤提示词模板。
        pass_condition: 通过条件（仅 review 步骤有意义）。
    """

    id: str
    type: Literal["generate", "review", "rewrite"]
    prompt: str
    pass_condition: Optional[str] = None


class SkillSchema(BaseModel):
    """定义一项 skill（技能），由多个步骤组成。

    Attributes:
        name: skill 名称。
        description: skill 描述。
        max_iterations: 最大迭代次数（review→rewrite 循环），默认 3。
        steps: 步骤列表（至少 1 个）。
    """

    name: str
    description: str
    max_iterations: int = Field(default=3, ge=1)
    steps: list[StepSchema] = Field(min_length=1)


class SSEEvent(BaseModel):
    """SSE 流式事件，用于服务端推送。

    Attributes:
        event: 事件类型 — chunk（文本块）、done（完成）、error（错误）、review_result（审阅结果）。
        content: 事件内容（文本块或消息）。
        passed: 审阅是否通过（仅 review_result 事件有意义）。
        issues: 审阅发现的问题列表（仅 review_result 事件有意义）。
    """

    event: Literal["chunk", "done", "error", "review_result"]
    content: str = ""
    passed: Optional[bool] = None
    issues: Optional[list[str]] = None


class SkillParseError(Exception):
    """Skill YAML/声明解析失败时抛出。"""

    pass


class SkillNotFoundError(Exception):
    """未找到指定 skill 时抛出。"""

    pass

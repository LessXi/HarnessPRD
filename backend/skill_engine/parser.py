"""Skill .md 文件解析器：YAML frontmatter 解析 + Jinja2 模板渲染。

用法::

    skill = parse_skill_file("skills/prd-generate.md")
    prompt = render_skill_prompt(skill.steps[0], {"form_data": {...}})
"""

import re
from pathlib import Path
from typing import Optional

import yaml
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from pydantic import ValidationError

from skill_engine.models import SkillParseError, SkillSchema, StepSchema

# 项目根目录（即 parser.py 所在文件的 ../..，即 backend/.. → 项目根）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _extract_frontmatter(content: str) -> str:
    """提取 ``---`` 分隔符之间的 YAML frontmatter 字符串。"""
    match = re.match(r"^---\s*\n(.*?)\n---[\s\n]", content, re.DOTALL)
    if not match:
        raise SkillParseError("文件缺少合法的 YAML frontmatter（---...---）")
    return match.group(1)


def _create_jinja_env(searchpath: Optional[str] = None) -> Environment:
    """创建 Jinja2 环境，FileSystemLoader 指向项目根目录（或指定路径）。

    Args:
        searchpath: 模板搜索路径，默认项目根目录。
    """
    if searchpath is None:
        searchpath = str(_PROJECT_ROOT)
    return Environment(
        loader=FileSystemLoader(searchpath),
        autoescape=False,
    )


def parse_skill_file(filepath: str) -> SkillSchema:
    """解析 ``.md`` skill 文件的 YAML frontmatter，返回 |SkillSchema|。

    文件格式::

        ---
        name: prd-generate
        description: 生成 PRD 文档
        max_iterations: 3
        steps:
          - id: generate
            type: generate
            prompt: 你是一名产品经理...
        ---
        （body 内容暂不处理）

    Args:
        filepath: skill 文件的路径。

    Returns:
        解析并校验后的 :class:`SkillSchema`。

    Raises:
        SkillParseError: 文件不存在、YAML 格式错误、或数据校验失败时抛出。
    """
    # 1) 读取文件内容
    try:
        content = Path(filepath).read_text(encoding="utf-8")
    except FileNotFoundError as e:
        logger.bind(event="skill_parse_error").warning(
            "Skill 文件不存在: {filepath}", filepath=filepath
        )
        raise SkillParseError(f"文件不存在: {filepath}") from e
    except OSError as e:
        logger.bind(event="skill_parse_error").warning(
            "读取 Skill 文件失败: {filepath} — {error}", filepath=filepath, error=str(e)
        )
        raise SkillParseError(f"读取文件失败: {filepath} — {e}") from e

    # 2) 提取 YAML frontmatter
    yaml_str = _extract_frontmatter(content)

    # 3) 解析 YAML
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        logger.bind(event="skill_parse_error").warning(
            "Skill YAML 格式错误: {filepath} — {error}", filepath=filepath, error=str(e)
        )
        raise SkillParseError(f"YAML 格式错误: {e}") from e

    if not isinstance(data, dict):
        logger.bind(event="skill_parse_error").warning(
            "Skill YAML frontmatter 非字典格式: {filepath}", filepath=filepath
        )
        raise SkillParseError("YAML frontmatter 必须为字典格式")

    # 4) Pydantic 校验 → SkillSchema
    try:
        return SkillSchema(**data)
    except ValidationError as e:
        logger.bind(event="skill_parse_error").warning(
            "Skill 数据校验失败: {filepath} — {error}", filepath=filepath, error=str(e)
        )
        raise SkillParseError(f"Skill 数据校验失败: {e}") from e


def render_skill_prompt(
    step: StepSchema,
    context: dict,
    searchpath: Optional[str] = None,
) -> str:
    """渲染步骤提示词模板。

    使用 Jinja2 渲染 ``step.prompt`` 中的模板变量。支持：

    - 简单变量替换 ``{{ product_name }}``
    - 嵌套变量 ``{{ form_data.product_name }}``
    - ``{% include \"path/to/template.md\" %}`` 标签（通过 FileSystemLoader）

    Args:
        step: 步骤定义（含 ``prompt`` 模板字符串）。
        context: 模板变量字典。
        searchpath: Jinja2 FileSystemLoader 搜索路径。
            默认项目根目录（即 ``backend/..``），使得 ``{% include \"docs/xxx.md\" %}`` 可工作。

    Returns:
        渲染后的文本。
    """
    env = _create_jinja_env(searchpath)
    template = env.from_string(step.prompt)
    return template.render(**context)

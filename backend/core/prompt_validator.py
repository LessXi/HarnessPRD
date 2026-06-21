"""模板字段引用校验器。

扫描 Jinja2 模板和 Skill Markdown 文件中的 ``{{ var_name }}`` 引用，
与 product_schema 字段白名单比对，报告无效引用。

用法：
    from core.prompt_validator import validate_all

    errors = validate_all()
    # => {"path/to/template.jinja2": ["invalid ref1", ...], ...}
"""

import re
from pathlib import Path
from typing import List

from loguru import logger

from core.field_registry import get_schema

# ── 上下文变量白名单 ──────────────────────────────────────────────
# 这些是引擎/服务层注入的全局上下文变量，非表单字段。
# form_data 是表单字段的容器（特殊处理：form_data.xxx 需校验 xxx 是否为合法字段）。
CONTEXT_WHITELIST: set = {
    "form_fields",
    "chat_log",
    "requirements_summary",
    "current_content",
    "prd_content",
    "api_content",
    "previous_content",
    "session_id",
    "doc_type",
    "base_prompt",
    "review_result",
}

# ── 编译正则 ─────────────────────────────────────────────────────
_MUSTACHE_RE = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)


# ======================================================================
# 内部工具
# ======================================================================


def _extract_var_name(expr: str) -> str | None:
    """从 Jinja2 表达式中提取主变量名。

    处理场景：
    - ``{{ var }}``                         → ``var``
    - ``{{ var | filter(args) }}``          → ``var``
    - ``{{ var or "default" }}``           → ``var``
    - ``{{ form_data.field }}``            → ``form_data.field``
    - ``{{ "literal" }}`` / ``{{ 42 }}``   → ``None``（跳过）
    """
    expr = expr.strip()

    # 去除管道过滤器
    expr = re.split(r"\s*\|\s*", expr)[0]
    # 去除 "or" 默认值
    expr = re.split(r"\s+or\s+", expr)[0]
    expr = expr.strip()

    # 跳过字符串字面量
    if (expr.startswith('"') and expr.endswith('"')) or (
        expr.startswith("'") and expr.endswith("'")
    ):
        return None
    # 跳过数字字面量
    try:
        float(expr)
        return None
    except ValueError:
        pass

    # 跳过空
    if not expr:
        return None

    return expr


def _iter_mustache_refs(content: str) -> list[str]:
    """遍历模板内容，返回所有 ``{{ }}`` 内提取后的变量名列表。"""
    refs: list[str] = []
    for m in _MUSTACHE_RE.finditer(content):
        var = _extract_var_name(m.group(1))
        if var is not None:
            refs.append(var)
    return refs


def _get_valid_form_fields() -> set:
    """从 product_schema 中提取有效字段名集合。"""
    schema = get_schema()
    return set(schema.get("properties", {}).keys())


# ======================================================================
# 公开 API
# ======================================================================


def validate_template(filepath: str) -> list[str]:
    """校验单个模板文件中的变量引用。

    返回无效引用的原始 ``{{ ... }}`` 字符串列表（含定界符，便于定位）。
    """
    path = Path(filepath)
    if not path.exists():
        logger.bind(event="prompt_validation").warning(
            "Template file not found: {path}", path=filepath
        )
        return ["FILE_NOT_FOUND"]

    content = path.read_text(encoding="utf-8")
    valid_fields = _get_valid_form_fields()
    refs = _iter_mustache_refs(content)

    invalid: list[str] = []

    for ref in refs:
        # form_data.field 特殊处理：校验 field 是否合法
        if ref.startswith("form_data."):
            field = ref[len("form_data.") :]
            if field not in valid_fields:
                invalid.append(f"{{{{ {ref} }}}}")
                logger.bind(event="prompt_validation").warning(
                    "Invalid form field reference in {path}: {ref}",
                    path=filepath,
                    ref=f"{{{{ {ref} }}}}",
                )
        elif "." in ref:
            # 带点的引用（如 f.label、item.value）是循环变量属性访问，
            # 无法静态校验，跳过。
            pass
        elif ref not in CONTEXT_WHITELIST:
            invalid.append(f"{{{{ {ref} }}}}")
            logger.bind(event="prompt_validation").warning(
                "Invalid context variable reference in {path}: {ref}",
                path=filepath,
                ref=f"{{{{ {ref} }}}}",
            )

    return invalid


def validate_all() -> dict[str, list[str]]:
    """校验所有已知模板文件。

    扫描范围：
    - ``backend/prompts/*.jinja2``
    - ``backend/skills/*.md``

    返回：``{filepath: [invalid_ref_str, ...]}``
    """
    backend_dir = Path(__file__).resolve().parent.parent
    results: dict[str, list[str]] = {}

    # --- jinja2 模板 ---
    for f in sorted(backend_dir.glob("prompts/*.jinja2")):
        errs = validate_template(str(f))
        if errs:
            results[str(f)] = errs

    # --- skill .md 文件 ---
    for f in sorted(backend_dir.glob("skills/*.md")):
        errs = validate_template(str(f))
        if errs:
            results[str(f)] = errs

    return results

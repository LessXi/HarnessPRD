"""字段注册表：以 questions_config.json 为单一来源，提供统一的字段元信息。

所有表单字段的定义、类型、顺序均由 questions_config.json 驱动。
后端代码不应再硬编码字段名。
"""

import json
from pathlib import Path
from typing import Any

_CONFIG_CACHE: dict | None = None


def _load() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        path = Path(__file__).resolve().parent / "questions_config.json"
        with path.open(encoding="utf-8") as f:
            _CONFIG_CACHE = json.load(f)
    return _CONFIG_CACHE


def get_all_fields() -> list[dict]:
    """合并 base + advanced 字段，返回完整列表"""
    cfg = _load()
    return cfg["base_questions"] + cfg["advanced_questions"]


def get_field_ids() -> list[str]:
    return [q["id"] for q in get_all_fields()]


def get_required_field_ids() -> list[str]:
    return [q["id"] for q in get_all_fields() if q.get("required")]


def get_optional_field_ids() -> list[str]:
    return [q["id"] for q in get_all_fields() if not q.get("required")]


def get_field(field_id: str) -> dict | None:
    for q in get_all_fields():
        if q["id"] == field_id:
            return q
    return None


def is_list_field(field_id: str) -> bool:
    """判断是否 list 类型（当前仅 mvp_features）"""
    f = get_field(field_id)
    return f is not None and f.get("type") == "list"

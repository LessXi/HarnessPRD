"""字段注册表：以 product_schema.json 为单一来源，提供统一的字段元信息。

Schema 优先读取 product_schema.json，失败时降级到 questions_config.json。
后端代码不应再硬编码字段名。
"""

import json
from pathlib import Path
from typing import Any

from loguru import logger

_CONFIG_CACHE: dict | None = None
_SCHEMA_CACHE: dict | None = None


def _load() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        path = Path(__file__).resolve().parent / "questions_config.json"
        with path.open(encoding="utf-8") as f:
            _CONFIG_CACHE = json.load(f)
    return _CONFIG_CACHE


def get_schema() -> dict:
    """返回完整 JSON Schema 对象。优先 product_schema.json，降级用 questions_config.json 重组。"""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE

    schema_path = Path(__file__).resolve().parent / "product_schema.json"
    try:
        with schema_path.open(encoding="utf-8") as f:
            _SCHEMA_CACHE = json.load(f)
        logger.bind(event="schema_loaded").info(
            "Schema loaded: version={version}, field_count={count}",
            version=_SCHEMA_CACHE.get("x-meta", {}).get("schema_version", "unknown"),
            count=len(_SCHEMA_CACHE.get("properties", {})),
        )
    except FileNotFoundError:
        logger.bind(event="schema_fallback").warning(
            "product_schema.json not found, falling back to questions_config.json"
        )
        _SCHEMA_CACHE = _build_schema_from_questions()
    except json.JSONDecodeError as e:
        logger.bind(event="schema_fallback").warning(
            "product_schema.json parse error: {error}, falling back to questions_config.json",
            error=str(e),
        )
        _SCHEMA_CACHE = _build_schema_from_questions()
    return _SCHEMA_CACHE


def _build_schema_from_questions() -> dict:
    """从 questions_config.json 临时构建 Schema 结构（降级路径）。"""
    cfg = _load()
    properties = {}
    required = []

    def _process(q_list: list, group: str) -> None:
        for q in q_list:
            fid = q["id"]
            prop: dict[str, Any] = {
                "x-ui": {
                    "label": q.get("label", fid),
                    "widget": q["type"],
                    "group": group,
                    "required": q.get("required", False),
                }
            }
            if "options" in q:
                prop["type"] = "string"
                prop["enum"] = [o["value"] for o in q["options"]]
            elif q["type"] == "list":
                prop["type"] = "array"
                prop["items"] = {"type": "string"}
                prop["minItems"] = 3
            else:
                prop["type"] = "string"
                # 降级路径为 required text/textarea 添加 minLength 约束
                if q.get("required"):
                    prop["minLength"] = 1
            if not q.get("required"):
                prop["default"] = ""
            properties[fid] = prop
            if q.get("required"):
                required.append(fid)

    _process(cfg["base_questions"], "base")
    _process(cfg["advanced_questions"], "advanced")

    return {
        "$schema": "https://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": properties,
        "required": required,
        "x-meta": {"schema_version": "0.0.0 (degraded)"},
    }


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

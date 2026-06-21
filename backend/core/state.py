"""数据模型定义（无状态架构）"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, create_model


# ========== 数据模型 ==========

class ChatMessage(BaseModel):
    role: str          # "user" | "assistant"
    content: str
    timestamp: datetime


class ReviewRound(BaseModel):
    round_number: int
    review_content: Optional[str] = None
    rewrite_content: Optional[str] = None


class DocumentState(BaseModel):
    content: str = ""
    streaming: bool = False
    last_chunk_at: Optional[datetime] = None
    review_rounds: list[ReviewRound] = []
    current_round: int = 0
    user_edits: Optional[str] = None
    confirmed: bool = False


# ========== 动态表单数据模型 ==========
# FormData 由 product_schema.json 动态生成，字段增减只需修改 JSON 文件。
# 类型映射：string→str, array→list[str], number→float, integer→int
# enum 字段使用 Literal 类型约束；required 列表控制必填/选填。

def _build_form_data_model():
    from typing import Literal
    from core.field_registry import get_schema

    schema = get_schema()
    properties = schema.get("properties", {})
    required_set = set(schema.get("required", []))
    fields = {}

    for name, prop in properties.items():
        json_type = prop.get("type")
        enum_vals = prop.get("enum")
        is_required = name in required_set

        # ── array → list[str] ──
        if json_type == "array":
            min_items = prop.get("minItems", 1)
            if is_required:
                fields[name] = (list[str], Field(min_length=min_items))
            else:
                fields[name] = (list[str], Field(default_factory=list, min_length=min_items))
            continue

        # ── enum → Literal[val1, val2, ...] ──
        if enum_vals:
            literal_type = Literal.__getitem__(tuple(enum_vals))
            if is_required:
                fields[name] = (literal_type, ...)
            else:
                fields[name] = (literal_type, Field(default=prop.get("default")))
            continue

        # ── string → str ──
        if json_type == "string":
            if is_required:
                fields[name] = (str, ...)
            else:
                default = prop.get("default", "")
                fields[name] = (str, Field(default=default))
            continue

        # ── number → float / integer → int (future-proof) ──
        if json_type in ("number", "integer"):
            py_type = float if json_type == "number" else int
            if is_required:
                fields[name] = (py_type, ...)
            else:
                fields[name] = (py_type, Field(default=prop.get("default", 0)))
            continue

        # ── fallback ──
        fields[name] = (str, Field(default=""))

    return create_model("FormData", **fields)


FormData = _build_form_data_model()

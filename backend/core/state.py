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
# FormData 由 questions_config.json 动态生成，字段增减只需修改 JSON

def _build_form_data_model():
    from core.field_registry import get_all_fields, is_list_field
    fields = {}
    for f in get_all_fields():
        fid = f["id"]
        required = f.get("required", False)
        if is_list_field(fid):
            fields[fid] = (list[str], Field(..., min_length=3))
        elif required:
            fields[fid] = (str, ...)
        else:
            fields[fid] = (str, Field(default=""))
    return create_model("FormData", **fields)

FormData = _build_form_data_model()

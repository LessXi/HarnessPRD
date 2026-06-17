"""状态机枚举、会话内存存储、状态转换校验"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, create_model
from enum import Enum


# ========== 枚举 ==========

class StateEnum(str, Enum):
    FORM_EDITING = "form_editing"
    AI_DIALOGUE = "ai_dialogue"
    GENERATING_PRD = "generating_prd"
    REVIEWING_PRD = "reviewing_prd"
    GENERATING_API = "generating_api"
    REVIEWING_API = "reviewing_api"
    GENERATING_PROMPTS = "generating_prompts"
    REVIEWING_PROMPTS = "reviewing_prompts"
    COMPLETED = "completed"


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


class SessionData(BaseModel):
    """统一会话数据，与 docs/session-data-structure.md 对齐"""

    # 基础字段
    session_id: str
    current_state: StateEnum = StateEnum.FORM_EDITING
    created_at: datetime

    # 步骤一：表单数据
    form_data: Optional[FormData] = None

    # 步骤二：AI 对话
    chat_messages: list[ChatMessage] = []
    requirements_summary: Optional[str] = None
    summary_confirmed: bool = False
    skip_dialogue: bool = False

    # 步骤三：三份文档
    prd: DocumentState = DocumentState()
    api: DocumentState = DocumentState()
    prompts: DocumentState = DocumentState()


# ========== 内存存储 ==========

class SessionStore:
    """Session 内存存储（dict），无数据库"""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}

    def create(self, form_data: FormData) -> SessionData:
        """创建新 session。如果达到上限则淘汰最旧的。"""
        from core.config import settings
        if len(self._sessions) >= settings.max_sessions:
            # 淘汰最旧的 session
            oldest_id = min(self._sessions.keys(), key=lambda sid: self._sessions[sid].created_at)
            self._sessions.pop(oldest_id)

        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        session = SessionData(
            session_id=session_id,
            created_at=now,
            form_data=form_data,
            current_state=StateEnum.AI_DIALOGUE,  # 提交表单后直接进入对话
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[SessionData]:
        return self._sessions.get(session_id)

    def update(self, session: SessionData) -> None:
        self._sessions[session.session_id] = session

    def list_recent(self, limit: int = 10) -> list[dict]:
        """返回最近会话摘要列表"""
        sorted_sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )
        result = []
        for s in sorted_sessions[:limit]:
            product_name = getattr(s.form_data, "product_name", "(未命名)") if s.form_data else "(未命名)"
            result.append({
                "session_id": s.session_id,
                "product_name": product_name,
                "current_state": s.current_state.value,
                "updated_at": s.created_at.isoformat(),
            })
        return result

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


# 全局单例
session_store = SessionStore()

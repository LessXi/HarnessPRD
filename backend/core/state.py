"""状态机枚举、会话内存存储、状态转换校验"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator
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


class FormData(BaseModel):
    """表单数据，与 docs/form-data-structure.md 对齐"""
    # base — required
    product_name: str = Field(..., description="产品名称")
    one_liner: str = Field(..., description="一句话定义")
    problem_statement: str = Field(..., description="核心痛点")
    target_users: str = Field(..., description="目标用户")
    mvp_features: list[str] = Field(..., min_length=3, description="MVP 功能列表（至少 3 条）")
    platform_type: str = Field(..., description="目标平台: web / mobile / wechat_miniprogram / desktop / multi")
    needs_auth: str = Field(..., description="是否需要登录: yes / no / unsure")
    needs_database: str = Field(..., description="是否需要数据库: yes / no / unsure")
    page_count: str = Field(..., description="页面数量: 1-3 / 4-10 / 10+ / unsure")

    # base — optional
    visual_style: str = Field(default="", description="视觉风格: minimal / creative / enterprise / unsure")
    competitors: str = Field(default="", description="竞品")

    # advanced — optional
    tech_stack_preference: str = Field(default="", description="技术栈偏好")
    feature_priority: str = Field(default="", description="功能优先级策略: user_defined / ai_suggest / iterate")
    doc_depth: str = Field(default="", description="文档详细程度: brief / standard / detailed")
    ai_temperature: str = Field(default="", description="AI 输出风格: conservative / balanced / creative")
    timeline_expectation: str = Field(default="", description="时间预期: 1-2_months / 3-6_months / 6+_months / unsure")
    additional_context: str = Field(default="", description="额外上下文")

    @field_validator("mvp_features")
    @classmethod
    def check_mvp_count(cls, v: list[str]) -> list[str]:
        if len(v) < 3:
            raise ValueError("至少需要 3 个 MVP 功能")
        return v


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
            product_name = s.form_data.product_name if s.form_data else "(未命名)"
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

"""统一的请求/响应 Pydantic 模型。

前端据此了解 API 的数据格式，Swagger 自动生成文档。
"""

from pydantic import BaseModel

from core.state import FormData


# ========== 请求模型（新无状态 API） ==========


class ChatRequest(BaseModel):
    """POST /api/chat/stream 的请求体"""
    session_id: str = ""
    form_data: FormData
    history: list[dict[str, str]] = []


class SummaryRequest(BaseModel):
    """POST /api/summary/generate 的请求体"""
    session_id: str = ""
    form_data: FormData
    history: list[dict[str, str]]


class DocumentRequest(BaseModel):
    """POST /api/documents/{type}/stream 的请求体"""
    session_id: str = ""
    form_data: FormData
    requirements_summary: str
    previous_content: str = ""
    prd_content: str = ""
    api_content: str = ""


class OptimizeRequest(BaseModel):
    """POST /api/documents/{type}/optimize 的请求体"""
    session_id: str = ""
    content: str
    form_data: FormData
    requirements_summary: str
    prd_content: str = ""
    api_content: str = ""


class DownloadRequest(BaseModel):
    """POST /api/documents/{type}/download 的请求体"""
    content: str


# ========== 响应模型 ==========


class SummaryResponse(BaseModel):
    """POST /api/summary/generate 的响应"""
    summary: str

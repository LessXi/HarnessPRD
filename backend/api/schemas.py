"""统一的请求/响应 Pydantic 模型。

前端据此了解 API 的数据格式，Swagger 自动生成文档。
请求模型也被复用为各路由的请求体类型，替换散落在路由文件中的内嵌模型。
"""

from pydantic import BaseModel


# ========== 请求模型 ==========

class MessageRequest(BaseModel):
    """POST /api/sessions/{id}/messages 的请求体"""
    content: str


class ContentRequest(BaseModel):
    """PUT /api/sessions/{id}/documents/{type}/content 的请求体"""
    content: str


# ========== 响应模型 ==========

class SessionCreatedResponse(BaseModel):
    """POST /api/sessions 创建成功的响应"""
    session_id: str
    current_state: str


class SessionSummary(BaseModel):
    """GET /api/sessions 列表中的每条摘要"""
    session_id: str
    product_name: str
    current_state: str
    updated_at: str


class SummaryResponse(BaseModel):
    """POST /api/sessions/{id}/summary/generate 的需求摘要"""
    summary: str


class ConfirmResponse(BaseModel):
    """确认类操作的响应，携带跳转到的下一步状态"""
    status: str
    next_state: str


class GenerateResponse(BaseModel):
    """触发文档生成后的响应"""
    status: str
    stream_url: str

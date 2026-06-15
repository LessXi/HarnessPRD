"""会话服务：创建 / 查询 / 校验 Session"""

from typing import Optional

from core.state import FormData, SessionData, session_store


def create_session(form_data: FormData) -> SessionData:
    """校验表单数据并创建 Session"""
    _validate_form(form_data)
    return session_store.create(form_data)


def get_session(session_id: str) -> Optional[SessionData]:
    """获取完整 SessionData"""
    return session_store.get(session_id)


def update_session(session: SessionData) -> None:
    """持久化更新后的 SessionData"""
    session_store.update(session)


def list_sessions(limit: int = 10) -> list[dict]:
    """列出最近会话摘要"""
    return session_store.list_recent(limit)


def _validate_form(data: FormData) -> None:
    """补充校验（Pydantic 字段校验之外）"""
    allowed_platform = {"web", "mobile", "wechat_miniprogram", "desktop", "multi"}
    if data.platform_type not in allowed_platform:
        raise ValueError(f"platform_type 必须是 {allowed_platform} 之一")

    allowed_auth = {"yes", "no", "unsure"}
    if data.needs_auth not in allowed_auth:
        raise ValueError(f"needs_auth 必须是 {allowed_auth} 之一")

    allowed_db = {"yes", "no", "unsure"}
    if data.needs_database not in allowed_db:
        raise ValueError(f"needs_database 必须是 {allowed_db} 之一")

    allowed_pages = {"1-3", "4-10", "10+", "unsure"}
    if data.page_count not in allowed_pages:
        raise ValueError(f"page_count 必须是 {allowed_pages} 之一")

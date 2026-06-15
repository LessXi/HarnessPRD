"""会话服务：创建 / 查询 / 校验 Session"""

from pathlib import Path
import json
from typing import Optional

from core.state import FormData, SessionData, session_store

# 加载表单配置，用于校验
_QUESTIONS_CONFIG_PATH = Path(__file__).resolve().parent.parent / "core" / "questions_config.json"
with open(_QUESTIONS_CONFIG_PATH, encoding="utf-8") as _f:
    _questions_config = json.load(_f)


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


def _load_questions() -> list[dict]:
    """将 base_questions 和 advanced_questions 合并为扁平列表"""
    return _questions_config.get("base_questions", []) + _questions_config.get("advanced_questions", [])


def _validate_form(data: FormData) -> None:
    """根据 questions_config.json 校验表单数据"""
    questions = _load_questions()
    data_dict = data.model_dump()

    for q in questions:
        qid = q["id"]
        value = data_dict.get(qid)

        # 必填检查
        if q.get("required") and not value:
            raise ValueError(f"{q['label']}（{qid}）是必填项")

        # 枚举值检查（select / radio 类型）
        options = q.get("options")
        if options and value:
            allowed = {o["value"] for o in options}
            if value not in allowed:
                raise ValueError(
                    f"{q['label']}（{qid}）的值 '{value}' 不在允许范围内，"
                    f"允许值: {allowed}"
                )

    # mvp_features 长度检查（Pydantic 模型已有 min_length=3，这里做兜底）
    if hasattr(data, "mvp_features") and data.mvp_features is not None:
        if len(data.mvp_features) < 3:
            raise ValueError("MVP 功能至少需要 3 条")

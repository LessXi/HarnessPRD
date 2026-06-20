"""会话服务：仅保留表单校验和问题配置加载"""

from pathlib import Path
import json

# 加载表单配置，用于校验
_QUESTIONS_CONFIG_PATH = Path(__file__).resolve().parent.parent / "core" / "questions_config.json"
with open(_QUESTIONS_CONFIG_PATH, encoding="utf-8") as _f:
    _questions_config = json.load(_f)


def _load_questions() -> list[dict]:
    """将 base_questions 和 advanced_questions 合并为扁平列表"""
    return _questions_config.get("base_questions", []) + _questions_config.get("advanced_questions", [])


def _validate_form(data: dict) -> None:
    """根据 questions_config.json 校验表单数据"""
    questions = _load_questions()

    for q in questions:
        qid = q["id"]
        value = data.get(qid)

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

    # mvp_features 长度检查
    mvp_features = data.get("mvp_features")
    if isinstance(mvp_features, list) and len(mvp_features) < 3:
        raise ValueError("MVP 功能至少需要 3 条")

"""Service 层纯函数测试（无需 LLM 调用）"""
import pytest
from core.field_registry import get_all_fields, get_field_ids, is_list_field
from services.session_service import _validate_form
from services.document_service import _has_issues, _build_prompt_kwargs


class TestFieldRegistry:
    """field_registry — questions_config.json 读取"""

    def test_get_all_fields_count(self):
        """返回 17 个字段（9 base + 8 advanced）"""
        fields = get_all_fields()
        assert len(fields) == 17

    def test_get_field_ids(self):
        """字段 ID 列表包含关键字段"""
        ids = get_field_ids()
        assert "product_name" in ids
        assert "one_liner" in ids
        assert "mvp_features" in ids
        assert "platform_type" in ids
        assert "additional_context" in ids

    def test_is_list_field_mvp(self):
        """mvp_features 被识别为 list 类型"""
        assert is_list_field("mvp_features") is True

    def test_is_list_field_text(self):
        """文本字段不被识别为 list"""
        assert is_list_field("product_name") is False

    def test_questions_config_fields(self, mock_form_data):
        """所有表单字段都存在 mock_form_data 中（动态 FormData 字段同步）"""
        for fid in get_field_ids():
            assert hasattr(mock_form_data, fid), f"FormData 缺少字段: {fid}"


class TestValidateForm:
    """session_service._validate_form — 表单校验"""

    def test_valid_form(self, mock_form_data):
        """有效表单不应抛出异常"""
        _validate_form(mock_form_data)

    def test_missing_required_field(self, mock_form_data):
        """必填字段为空时抛出 ValueError"""
        import copy
        data = copy.deepcopy(mock_form_data)
        data.product_name = ""
        with pytest.raises(ValueError, match="产品名称"):
            _validate_form(data)

    def test_invalid_select_value(self, mock_form_data):
        """select 字段传入非允许值时抛出 ValueError"""
        import copy
        data = copy.deepcopy(mock_form_data)
        data.platform_type = "invalid_platform"
        with pytest.raises(ValueError, match="目标平台"):
            _validate_form(data)

    def test_invalid_radio_value(self, mock_form_data):
        """radio 字段传入非允许值时抛出 ValueError"""
        import copy
        data = copy.deepcopy(mock_form_data)
        data.needs_auth = "maybe"
        with pytest.raises(ValueError, match="用户登录"):
            _validate_form(data)


class TestHasIssues:
    """document_service._has_issues — 审核结果判断"""

    def test_passed(self):
        """包含"审核通过"返回 False"""
        assert _has_issues("一切正常，审核通过") is False

    def test_passed_with_extra(self):
        """包含"审核通过"但有其他内容仍返回 False"""
        assert _has_issues("审核通过\n建议改进：无") is False

    def test_failed_with_issues(self):
        """不包含"审核通过"返回 True"""
        assert _has_issues("问题1：缺少用户场景描述") is True

    def test_failed_empty(self):
        """空字符串返回 True"""
        assert _has_issues("") is True

    def test_failed_with_review_keyword(self):
        """包含"审核不通过"等近似字符串"""
        assert _has_issues("审核不通过，需要修改") is True


class TestBuildPromptKwargs:
    """document_service._build_prompt_kwargs — Prompt 上下文构造"""

    def test_prd_kwargs(self, mock_session):
        """PRD 只需要 form_data + requirements_summary"""
        kwargs = _build_prompt_kwargs(mock_session, "prd")
        assert "form_data" in kwargs
        assert "requirements_summary" in kwargs
        assert "prd_content" not in kwargs
        assert "api_content" not in kwargs

    def test_api_kwargs(self, mock_session):
        """API 文档需要 form_data + summary + prd_content"""
        mock_session.prd.content = "测试 PRD 内容"
        kwargs = _build_prompt_kwargs(mock_session, "api")
        assert "form_data" in kwargs
        assert "requirements_summary" in kwargs
        assert kwargs.get("prd_content") == "测试 PRD 内容"
        assert "api_content" not in kwargs

    def test_prompts_kwargs(self, mock_session):
        """提示词套件需要 form_data + summary + prd_content + api_content"""
        mock_session.prd.content = "测试 PRD 内容"
        mock_session.api.content = "测试 API 内容"
        kwargs = _build_prompt_kwargs(mock_session, "prompts")
        assert kwargs.get("prd_content") == "测试 PRD 内容"
        assert kwargs.get("api_content") == "测试 API 内容"

    def test_kwargs_no_form_data(self):
        """form_data 为 None 时返回空字典"""
        from unittest.mock import MagicMock
        session = MagicMock()
        session.form_data = None
        session.requirements_summary = ""
        kwargs = _build_prompt_kwargs(session, "prd")
        assert kwargs["form_data"] == {}

"""Service 层纯函数测试（无需 LLM 调用）"""
import copy
import pytest
from core.field_registry import get_all_fields, get_field_ids, is_list_field
from services.session_service import _validate_form
from services.document_service import _build_prompt_kwargs


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
    """session_service._validate_form — 表单校验（新签名：接受 dict）"""

    def test_valid_form(self, mock_form_dict):
        """有效表单不应抛出异常"""
        _validate_form(mock_form_dict)

    def test_missing_required_field(self, mock_form_dict):
        """必填字段为空时抛出 ValueError"""
        data = copy.deepcopy(mock_form_dict)
        data["product_name"] = ""
        with pytest.raises(ValueError, match="产品名称"):
            _validate_form(data)

    def test_invalid_select_value(self, mock_form_dict):
        """select 字段传入非允许值时抛出 ValueError"""
        data = copy.deepcopy(mock_form_dict)
        data["platform_type"] = "invalid_platform"
        with pytest.raises(ValueError, match="目标平台"):
            _validate_form(data)

    def test_invalid_radio_value(self, mock_form_dict):
        """radio 字段传入非允许值时抛出 ValueError"""
        data = copy.deepcopy(mock_form_dict)
        data["needs_auth"] = "maybe"
        with pytest.raises(ValueError, match="用户登录"):
            _validate_form(data)



class TestBuildPromptKwargs:
    """document_service._build_prompt_kwargs — Prompt 上下文构造（新无状态签名）"""

    def test_prd_kwargs(self, mock_form_dict):
        """PRD 只需要 form_data + requirements_summary"""
        kwargs = _build_prompt_kwargs(
            mock_form_dict, "需求摘要",
            doc_type="prd",
        )
        assert kwargs["form_data"] == mock_form_dict
        assert kwargs["requirements_summary"] == "需求摘要"
        assert "prd_content" not in kwargs
        assert "api_content" not in kwargs

    def test_api_kwargs(self, mock_form_dict):
        """API 文档需要 form_data + summary + prd_content"""
        kwargs = _build_prompt_kwargs(
            mock_form_dict, "需求摘要",
            doc_type="api",
            prd_content="测试 PRD 内容",
        )
        assert kwargs["form_data"] == mock_form_dict
        assert kwargs["requirements_summary"] == "需求摘要"
        assert kwargs["prd_content"] == "测试 PRD 内容"
        assert "api_content" not in kwargs

    def test_prompts_kwargs(self, mock_form_dict):
        """提示词套件需要 form_data + summary + prd_content + api_content"""
        kwargs = _build_prompt_kwargs(
            mock_form_dict, "需求摘要",
            doc_type="prompts",
            prd_content="测试 PRD 内容",
            api_content="测试 API 内容",
        )
        assert kwargs["prd_content"] == "测试 PRD 内容"
        assert kwargs["api_content"] == "测试 API 内容"

    def test_kwargs_empty_form_data(self):
        """空 form_data 仍正常工作"""
        kwargs = _build_prompt_kwargs(
            {}, "摘要",
            doc_type="prd",
        )
        assert kwargs["form_data"] == {}
        assert kwargs["requirements_summary"] == "摘要"

    def test_previous_content(self, mock_form_dict):
        """previous_content 字段被正确传递"""
        kwargs = _build_prompt_kwargs(
            mock_form_dict, "摘要",
            doc_type="prd",
            previous_content="已生成的内容",
        )
        assert kwargs["previous_content"] == "已生成的内容"

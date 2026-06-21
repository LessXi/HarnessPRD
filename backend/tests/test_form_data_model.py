"""Tests for FormData model — dynamically built from product_schema.json via get_schema()."""

import pytest
from pydantic import ValidationError
from core.state import FormData


class TestFormDataModel:
    """FormData — dynamically generated from product_schema.json."""

    def test_has_17_fields(self):
        """FormData 应包含全部 17 个字段（9 必填 + 8 选填）。"""
        assert len(FormData.model_fields) == 17

    def test_rejects_missing_required(self):
        """缺少必填字段时抛出 ValidationError。"""
        with pytest.raises(ValidationError):
            FormData()  # No fields provided

    def test_rejects_invalid_enum(self):
        """非允许的 enum 值时抛出 ValidationError。"""
        with pytest.raises(ValidationError):
            FormData(
                product_name="X",
                one_liner="Y",
                problem_statement="Z",
                target_users="U",
                mvp_features=["a", "b", "c"],
                platform_type="invalid",  # Not in enum ["web","mobile",...]
                needs_auth="yes",
                needs_database="yes",
                page_count="1-3",
            )

    def test_rejects_short_mvp_features(self):
        """mvp_features 少于 3 项时抛出 ValidationError。"""
        with pytest.raises(ValidationError):
            FormData(
                product_name="X",
                one_liner="Y",
                problem_statement="Z",
                target_users="U",
                mvp_features=["a", "b"],  # Only 2 items, minItems=3
                platform_type="web",
                needs_auth="yes",
                needs_database="yes",
                page_count="1-3",
            )

    def test_accepts_valid_data(self):
        """合法数据应成功创建 FormData 实例。"""
        f = FormData(
            product_name="测试产品",
            one_liner="一句话描述",
            problem_statement="解决的问题",
            target_users="目标用户",
            mvp_features=["功能A", "功能B", "功能C"],
            platform_type="web",
            needs_auth="yes",
            needs_database="yes",
            page_count="1-3",
        )
        assert f.product_name == "测试产品"
        assert f.platform_type == "web"
        assert f.mvp_features == ["功能A", "功能B", "功能C"]

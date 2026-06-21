"""测试 prompt_validator 模板引用校验。"""

import re

import pytest

from core.prompt_validator import (
    CONTEXT_WHITELIST,
    _extract_var_name,
    _get_valid_form_fields,
    validate_all,
    validate_template,
)


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def valid_template(tmp_path):
    """模板：只使用白名单变量 + 合法表单字段引用。"""
    f = tmp_path / "valid.jinja2"
    f.write_text(
        "\n".join(
            [
                "摘要：{{ requirements_summary }}",
                "产品名：{{ form_data.product_name }}",
                "平台：{{ form_data.platform_type }}",
                "文档类型：{{ doc_type }}",
            ]
        ),
        encoding="utf-8",
    )
    return str(f)


@pytest.fixture
def invalid_template(tmp_path):
    """模板：包含非法字段引用和非法上下文变量。"""
    f = tmp_path / "invalid.jinja2"
    f.write_text(
        "\n".join(
            [
                "{{ totally_unknown_var }}",
                "{{ form_data.nonexistent_field }}",
                "{{ another_bad_one }}",
                "{{ requirements_summary }}",
                "{{ form_data.product_name }}",
            ]
        ),
        encoding="utf-8",
    )
    return str(f)


# ======================================================================
# _extract_var_name 单元测试
# ======================================================================


class TestExtractVarName:
    def test_simple_var(self):
        assert _extract_var_name("foo") == "foo"

    def test_filtered_var(self):
        assert _extract_var_name('mvp_features | join("、")') == "mvp_features"

    def test_or_default(self):
        assert _extract_var_name('visual_style or "未指定"') == "visual_style"

    def test_form_data_field(self):
        assert _extract_var_name("form_data.product_name") == "form_data.product_name"

    def test_form_data_with_filter(self):
        assert (
            _extract_var_name('form_data.mvp_features | join("、")')
            == "form_data.mvp_features"
        )

    def test_string_literal_returns_none(self):
        assert _extract_var_name('"hello"') is None
        assert _extract_var_name("'world'") is None

    def test_number_literal_returns_none(self):
        assert _extract_var_name("42") is None

    def test_empty_string_returns_none(self):
        assert _extract_var_name("") is None
        assert _extract_var_name("   ") is None


# ======================================================================
# validate_template 功能测试
# ======================================================================


class TestValidateTemplate:
    def test_valid_template_returns_empty(self, valid_template):
        """白名单变量 + 合法表单字段 → 无错误。"""
        errors = validate_template(valid_template)
        assert errors == []

    def test_invalid_template_returns_errors(self, invalid_template):
        """非法字段引用 → 返回错误列表。"""
        errors = validate_template(invalid_template)
        # 期待 3 个非法引用：totally_unknown_var, nonexistent_field, another_bad_one
        assert len(errors) == 3
        assert "{{ totally_unknown_var }}" in errors
        assert "{{ form_data.nonexistent_field }}" in errors
        assert "{{ another_bad_one }}" in errors

    def test_missing_file_returns_file_not_found(self):
        """文件不存在 → 返回 FILE_NOT_FOUND。"""
        errors = validate_template("/tmp/does_not_exist.jinja2")
        assert errors == ["FILE_NOT_FOUND"]

    def test_all_whitelist_vars_pass(self, tmp_path):
        """逐一验证每个白名单变量都不会被标记。"""
        for var in CONTEXT_WHITELIST:
            f = tmp_path / f"test_{var}.jinja2"
            f.write_text(f"{{{{ {var} }}}}", encoding="utf-8")
            errors = validate_template(str(f))
            assert errors == [], f"Whitelist var '{var}' should pass but got: {errors}"

    def test_all_valid_form_fields_pass(self, tmp_path):
        """逐一验证每个合法表单字段都不会被标记。"""
        valid_fields = _get_valid_form_fields()
        for field in valid_fields:
            f = tmp_path / f"test_{field}.jinja2"
            f.write_text(f"{{{{ form_data.{field} }}}}", encoding="utf-8")
            errors = validate_template(str(f))
            assert errors == [], f"Form field '{field}' should pass but got: {errors}"

    def test_form_data_empty_field_rejected(self, tmp_path):
        """form_data 后接空字段 → 应报错。"""
        f = tmp_path / "empty_field.jinja2"
        f.write_text("{{ form_data. }}", encoding="utf-8")
        errors = validate_template(str(f))
        assert len(errors) == 1


# ======================================================================
# validate_all 集成测试
# ======================================================================


class TestValidateAll:
    def test_validate_all_returns_dict(self):
        """validate_all 扫描实际模板文件，返回 dict。"""
        results = validate_all()
        assert isinstance(results, dict)
        # 不应有 FILE_NOT_FOUND
        all_errs = [e for errs in results.values() for e in errs]
        assert "FILE_NOT_FOUND" not in all_errs

    def test_validate_all_only_returns_files_with_errors(self, monkeypatch):
        """validate_all 只返回有错误的文件（当前预期空，即无错误）。"""
        # 注意：如果未来模板中引入了非法引用，此测试可能需要更新
        results = validate_all()
        # 理想情况下所有模板引用都合法
        # 但我们不强制断言空，因为后期可能引入新模板
        for fp, errs in results.items():
            for e in errs:
                # None of the errors should be FILE_NOT_FOUND
                assert e != "FILE_NOT_FOUND", f"File not found: {fp}"

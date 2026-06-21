"""测试 skill_engine.parser — parse_skill_file + render_skill_prompt。"""

from pathlib import Path

import pytest

from skill_engine.models import SkillSchema, SkillParseError, StepSchema
from skill_engine.parser import parse_skill_file, render_skill_prompt


# ============================================================
# RED: 先写测试，确认失败后再实现 parser.py
# ============================================================


class TestParseSkillFile:
    """parse_skill_file — YAML frontmatter 解析"""

    def test_parse_valid_skill_file(self, tmp_path: Path):
        """合法 skill 文件 → 返回 SkillSchema"""
        skill_file = tmp_path / "valid-skill.md"
        skill_file.write_text(
            "---\n"
            "name: test-skill\n"
            "description: 测试技能\n"
            "max_iterations: 3\n"
            "steps:\n"
            "  - id: generate\n"
            "    type: generate\n"
            "    prompt: 生成内容\n"
            "  - id: review\n"
            "    type: review\n"
            "    prompt: 审阅内容\n"
            "    pass_condition: 通过\n"
            "---\n"
            "\n"
            "Body 说明文本\n",
            encoding="utf-8",
        )
        skill = parse_skill_file(str(skill_file))
        assert isinstance(skill, SkillSchema)
        assert skill.name == "test-skill"
        assert skill.description == "测试技能"
        assert skill.max_iterations == 3
        assert len(skill.steps) == 2
        assert skill.steps[0].id == "generate"
        assert skill.steps[0].type == "generate"
        assert skill.steps[0].prompt == "生成内容"
        assert skill.steps[1].type == "review"
        assert skill.steps[1].pass_condition == "通过"

    def test_parse_minimal(self, tmp_path: Path):
        """最小必需字段 → 默认 max_iterations=3"""
        skill_file = tmp_path / "minimal.md"
        skill_file.write_text(
            "---\n"
            "name: minimal\n"
            "description: 最小技能\n"
            "steps:\n"
            "  - id: s1\n"
            "    type: generate\n"
            "    prompt: gen\n"
            "---\n",
            encoding="utf-8",
        )
        skill = parse_skill_file(str(skill_file))
        assert skill.name == "minimal"
        assert skill.max_iterations == 3  # 默认值
        assert len(skill.steps) == 1

    def test_parse_missing_name(self, tmp_path: Path):
        """缺 name 字段 → SkillParseError"""
        skill_file = tmp_path / "no-name.md"
        skill_file.write_text(
            "---\n"
            "description: 缺 name\n"
            "steps:\n"
            "  - id: s1\n"
            "    type: generate\n"
            "    prompt: test\n"
            "---\n",
            encoding="utf-8",
        )
        with pytest.raises(SkillParseError):
            parse_skill_file(str(skill_file))

    def test_parse_no_frontmatter(self, tmp_path: Path):
        """无 frontmatter 分隔符 → SkillParseError"""
        skill_file = tmp_path / "no-fm.md"
        skill_file.write_text("纯文本，没有 YAML frontmatter\n", encoding="utf-8")
        with pytest.raises(SkillParseError):
            parse_skill_file(str(skill_file))

    def test_parse_invalid_yaml(self, tmp_path: Path):
        """YAML 格式错误 → SkillParseError"""
        skill_file = tmp_path / "bad-yaml.md"
        skill_file.write_text(
            "---\n"
            "name: test\n"
            "description: {{ broken yaml\n"
            "---\n",
            encoding="utf-8",
        )
        with pytest.raises(SkillParseError):
            parse_skill_file(str(skill_file))

    def test_parse_empty_frontmatter(self, tmp_path: Path):
        """frontmatter 为空 → SkillParseError"""
        skill_file = tmp_path / "empty-fm.md"
        skill_file.write_text("---\n---\n", encoding="utf-8")
        with pytest.raises(SkillParseError):
            parse_skill_file(str(skill_file))

    def test_parse_file_not_found(self):
        """文件不存在 → SkillParseError"""
        with pytest.raises(SkillParseError):
            parse_skill_file("/tmp/does-not-exist.md")


class TestRenderSkillPrompt:
    """render_skill_prompt — Jinja2 模板渲染"""

    def test_simple_variable(self):
        """简单 {{ variable }} 替换"""
        step = StepSchema(id="s1", type="generate", prompt="产品名称：{{ product_name }}")
        result = render_skill_prompt(step, {"product_name": "智能简历助手"})
        assert result == "产品名称：智能简历助手"

    def test_nested_variable(self):
        """嵌套 {{ form_data.product_name }} 替换"""
        step = StepSchema(
            id="s1", type="generate", prompt="产品：{{ form_data.product_name }}"
        )
        result = render_skill_prompt(
            step, {"form_data": {"product_name": "智能简历"}}
        )
        assert result == "产品：智能简历"

    def test_multiple_variables(self):
        """多个变量同时替换"""
        step = StepSchema(
            id="s1",
            type="generate",
            prompt="产品：{{ name }}，平台：{{ platform }}",
        )
        result = render_skill_prompt(
            step, {"name": "记账工具", "platform": "Web"}
        )
        assert result == "产品：记账工具，平台：Web"

    def test_runtime_variable_current_content(self):
        """{{ current_content }} 由 engine 在运行时注入，parser 直接渲染"""
        step = StepSchema(
            id="s1", type="review", prompt="审阅内容：{{ current_content }}"
        )
        result = render_skill_prompt(
            step, {"current_content": "这是要审阅的文档"}
        )
        assert result == "审阅内容：这是要审阅的文档"

    def test_runtime_variable_review_result(self):
        """{{ review_result }} 由 engine 注入"""
        step = StepSchema(
            id="s1", type="rewrite", prompt="根据审核意见重写：{{ review_result }}"
        )
        result = render_skill_prompt(
            step, {"review_result": "需要补充细节"}
        )
        assert result == "根据审核意见重写：需要补充细节"

    def test_include_directive(self, tmp_path: Path):
        """{% include %} 标签正确加载外部模板文件"""
        # 在临时目录下创建 docs/prd-template.md
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        template_file = docs_dir / "prd-template.md"
        template_file.write_text("这是 PRD 模板内容", encoding="utf-8")

        step = StepSchema(
            id="s1",
            type="generate",
            prompt="内容如下：{% include \"docs/prd-template.md\" %}",
        )
        # 传入 searchpath 指向 tmp_path，使 Jinja2 能找到 docs/ 子目录
        result = render_skill_prompt(step, {}, searchpath=str(tmp_path))
        assert "这是 PRD 模板内容" in result

    def test_empty_context(self):
        """空 context 不抛异常，纯文本提示词原样输出"""
        step = StepSchema(id="s1", type="generate", prompt="纯文本提示词")
        result = render_skill_prompt(step, {})
        assert result == "纯文本提示词"

    def test_undefined_variable_renders_empty(self):
        """未定义变量渲染为空字符串（Jinja2 Undefined 默认行为）"""
        step = StepSchema(id="s1", type="generate", prompt="名称：{{ undefined_var }}")
        result = render_skill_prompt(step, {})
        assert result == "名称："

    def test_multiline_prompt(self):
        """多行 prompt 模板保持换行"""
        step = StepSchema(
            id="s1",
            type="generate",
            prompt="第一行\n第二行\n第三行：{{ value }}",
        )
        result = render_skill_prompt(step, {"value": "hello"})
        assert result == "第一行\n第二行\n第三行：hello"

"""测试 skill_engine.loader — SkillLoader 热加载。"""

from pathlib import Path

import pytest

from skill_engine.models import SkillSchema, SkillNotFoundError
from skill_engine.parser import parse_skill_file


# ============================================================
# RED: 先写测试，确认 loader.py 尚不存在或实现不完整时失败
# ============================================================


_SKILL_A = """---
name: prd-generate
description: 生成 PRD 文档
max_iterations: 3
steps:
  - id: generate
    type: generate
    prompt: 生成 PRD 内容
---
"""

_SKILL_B = """---
name: api-generate
description: 生成 API 文档
max_iterations: 3
steps:
  - id: generate
    type: generate
    prompt: 生成 API 内容
---
"""

_SKILL_C = """---
name: prompts-generate
description: 生成提示词套件
max_iterations: 3
steps:
  - id: generate
    type: generate
    prompt: 生成提示词内容
---
"""


class TestSkillLoaderInit:
    """SkillLoader.__init__ — 构造时自动 load_all"""

    def test_empty_directory(self, tmp_path: Path):
        """空目录 → 空缓存，不抛异常"""
        from skill_engine.loader import SkillLoader

        loader = SkillLoader(str(tmp_path))
        assert len(loader.list_skills()) == 0
        assert loader._cache == {}

    def test_load_three_skills(self, tmp_path: Path):
        """目录有 3 个 skill 文件 → 缓存 3 个 entry"""
        for name, content in [
            ("prd-generate.md", _SKILL_A),
            ("api-generate.md", _SKILL_B),
            ("prompts-generate.md", _SKILL_C),
        ]:
            (tmp_path / name).write_text(content, encoding="utf-8")

        from skill_engine.loader import SkillLoader

        loader = SkillLoader(str(tmp_path))
        assert len(loader._cache) == 3
        assert "prd-generate" in loader._cache
        assert "api-generate" in loader._cache
        assert "prompts-generate" in loader._cache

    def test_ignore_non_md_files(self, tmp_path: Path):
        """非 .md 文件被忽略"""
        (tmp_path / "prd-generate.md").write_text(_SKILL_A, encoding="utf-8")
        (tmp_path / "notes.txt").write_text("not a skill", encoding="utf-8")
        (tmp_path / "data.json").write_text('{"key": "val"}', encoding="utf-8")

        from skill_engine.loader import SkillLoader

        loader = SkillLoader(str(tmp_path))
        assert len(loader._cache) == 1

    def test_parse_error_skill_skipped(self, tmp_path: Path):
        """无效 skill 文件 → 记录警告并跳过，不阻塞整体加载"""
        (tmp_path / "bad.md").write_text("纯文本无 frontmatter\n", encoding="utf-8")

        from skill_engine.loader import SkillLoader

        loader = SkillLoader(str(tmp_path))
        # 坏文件被跳过，缓存为空
        assert len(loader._cache) == 0


class TestSkillLoaderGet:
    """SkillLoader.get — 按 name 获取 SkillSchema"""

    def test_get_existing_skill(self, tmp_path: Path):
        """get("prd-generate") → 返回 SkillSchema"""
        (tmp_path / "prd-generate.md").write_text(_SKILL_A, encoding="utf-8")

        from skill_engine.loader import SkillLoader

        loader = SkillLoader(str(tmp_path))
        skill = loader.get("prd-generate")
        assert isinstance(skill, SkillSchema)
        assert skill.name == "prd-generate"
        assert skill.description == "生成 PRD 文档"
        assert len(skill.steps) == 1

    def test_get_nonexistent_skill(self, tmp_path: Path):
        """get("nonexistent") → SkillNotFoundError"""
        (tmp_path / "prd-generate.md").write_text(_SKILL_A, encoding="utf-8")

        from skill_engine.loader import SkillLoader

        loader = SkillLoader(str(tmp_path))
        with pytest.raises(SkillNotFoundError) as exc_info:
            loader.get("nonexistent")
        assert "nonexistent" in str(exc_info.value)

    def test_get_case_sensitive(self, tmp_path: Path):
        """name 匹配区分大小写"""
        (tmp_path / "Prd-Generate.md").write_text(_SKILL_A.replace(
            "prd-generate", "Prd-Generate"
        ), encoding="utf-8")

        from skill_engine.loader import SkillLoader

        loader = SkillLoader(str(tmp_path))
        skill = loader.get("Prd-Generate")
        assert skill.name == "Prd-Generate"

        with pytest.raises(SkillNotFoundError):
            loader.get("prd-generate")


class TestSkillLoaderReload:
    """SkillLoader.reload — 运行时热加载"""

    def test_reload_detects_new_files(self, tmp_path: Path):
        """reload() 后新文件被识别"""
        (tmp_path / "prd-generate.md").write_text(_SKILL_A, encoding="utf-8")

        from skill_engine.loader import SkillLoader

        loader = SkillLoader(str(tmp_path))
        assert len(loader._cache) == 1

        # 新增文件
        (tmp_path / "api-generate.md").write_text(_SKILL_B, encoding="utf-8")
        loader.reload()
        assert len(loader._cache) == 2
        assert "api-generate" in loader._cache

    def test_reload_removes_deleted_files(self, tmp_path: Path):
        """reload() 后删除的文件从缓存移除"""
        (tmp_path / "prd-generate.md").write_text(_SKILL_A, encoding="utf-8")
        (tmp_path / "api-generate.md").write_text(_SKILL_B, encoding="utf-8")

        from skill_engine.loader import SkillLoader

        loader = SkillLoader(str(tmp_path))
        assert len(loader._cache) == 2

        # 删除文件
        (tmp_path / "prd-generate.md").unlink()
        loader.reload()
        assert len(loader._cache) == 1
        assert "api-generate" in loader._cache
        with pytest.raises(SkillNotFoundError):
            loader.get("prd-generate")

    def test_reload_updates_modified_skills(self, tmp_path: Path):
        """reload() 后修改的文件更新缓存"""
        (tmp_path / "prd-generate.md").write_text(_SKILL_A, encoding="utf-8")

        from skill_engine.loader import SkillLoader

        loader = SkillLoader(str(tmp_path))
        assert loader.get("prd-generate").description == "生成 PRD 文档"

        # 修改文件
        modified = _SKILL_A.replace("生成 PRD 文档", "生成 PRD 文档（v2）")
        (tmp_path / "prd-generate.md").write_text(modified, encoding="utf-8")
        loader.reload()
        assert loader.get("prd-generate").description == "生成 PRD 文档（v2）"

    def test_reload_atomic_swap(self, tmp_path: Path):
        """reload() 原子替换：构建新 dict 后再赋值"""
        (tmp_path / "prd-generate.md").write_text(_SKILL_A, encoding="utf-8")

        from skill_engine.loader import SkillLoader

        loader = SkillLoader(str(tmp_path))
        old_cache = loader._cache

        (tmp_path / "api-generate.md").write_text(_SKILL_B, encoding="utf-8")
        loader.reload()

        # 缓存引用已被替换（新 dict 对象）
        assert loader._cache is not old_cache
        assert len(loader._cache) == 2


class TestSkillLoaderListSkills:
    """SkillLoader.list_skills — 列出所有 skill 名称"""

    def test_list_skills(self, tmp_path: Path):
        """list_skills() 返回所有 skill name 列表"""
        (tmp_path / "prd-generate.md").write_text(_SKILL_A, encoding="utf-8")
        (tmp_path / "api-generate.md").write_text(_SKILL_B, encoding="utf-8")

        from skill_engine.loader import SkillLoader

        loader = SkillLoader(str(tmp_path))
        names = loader.list_skills()
        assert sorted(names) == sorted(["prd-generate", "api-generate"])

    def test_list_skills_empty(self, tmp_path: Path):
        """空目录 → list_skills() 返回空列表"""
        from skill_engine.loader import SkillLoader

        loader = SkillLoader(str(tmp_path))
        assert loader.list_skills() == []

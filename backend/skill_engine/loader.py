"""Skill Loader 热加载：扫描目录、解析、缓存 SkillSchema。

典型用法::

    loader = SkillLoader("backend/skills")
    skill = loader.get("prd-generate")
    loader.reload()  # 运行时热加载
"""

import glob
import logging
import os

from skill_engine.models import SkillNotFoundError, SkillSchema
from skill_engine.parser import parse_skill_file

logger = logging.getLogger(__name__)


class SkillLoader:
    """Skill 加载器。构造时自动扫描 ``skills_dir/*.md`` 并缓存。

    Args:
        skills_dir: 包含 ``.md`` skill 文件的目录路径。

    线程安全说明：
        ``reload()`` 使用原子替换（先构建新 dict 再赋值 ``self._cache``），
        在 GIL 保护下对单线程应用是安全的。多线程场景下读取 ``_cache`` 时
        可能短暂读到旧引用，但不会读到损坏状态。
    """

    def __init__(self, skills_dir: str) -> None:
        self.skills_dir = os.path.abspath(skills_dir)
        self._cache: dict[str, SkillSchema] = {}
        self.load_all()

    # ------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------

    def load_all(self) -> None:
        """扫描 ``skills_dir/*.md``，解析并构建新缓存。

        原子替换：先构建 ``new_cache``，再赋值 ``self._cache``。
        目录不存在或不含任何 ``.md`` 文件时缓存为空，不抛异常。
        """
        new_cache: dict[str, SkillSchema] = {}
        pattern = os.path.join(self.skills_dir, "*.md")
        for filepath in glob.glob(pattern):
            try:
                skill = parse_skill_file(filepath)
                new_cache[skill.name] = skill
                logger.debug("Loaded skill: %s from %s", skill.name, filepath)
            except Exception:
                logger.exception("Failed to parse skill file: %s", filepath)
                raise
        self._cache = new_cache
        logger.info(
            "SkillLoader loaded %d skill(s) from %s",
            len(new_cache),
            self.skills_dir,
        )

    def get(self, name: str) -> SkillSchema:
        """按 name 获取已缓存的 |SkillSchema|。

        Args:
            name: skill 名称（区分大小写）。

        Returns:
            对应的 |SkillSchema|。

        Raises:
            SkillNotFoundError: 未找到指定 skill。
        """
        skill = self._cache.get(name)
        if skill is None:
            raise SkillNotFoundError(f"Skill '{name}' 未找到（可用: {list(self._cache.keys())}）")
        return skill

    def reload(self) -> None:
        """运行时热加载：重新扫描目录，原子替换缓存。"""
        self.load_all()

    def list_skills(self) -> list[str]:
        """返回所有已缓存的 skill 名称列表。"""
        return list(self._cache.keys())

"""Skill 可见性与手动管理 API

提供能力：
  - GET  /api/skills          → 返回已加载 skill 列表
  - POST /api/skills/reload   → 热加载 skill 文件（运行时刷新）
"""

from fastapi import APIRouter

# 使用模块属性引用，确保测试时 patch 生效（import 后读取动态属性）
import services.document_service as ds

router = APIRouter(prefix="/api")


@router.get("/skills")
async def list_skills():
    """返回所有已加载的 skill 概要信息。"""
    loader = ds._skill_loader
    if loader is None:
        return {"skills": []}

    results: list[dict] = []
    for name in loader.list_skills():
        skill = loader.get(name)
        results.append({
            "name": skill.name,
            "description": skill.description,
            "steps": len(skill.steps),
        })
    return {"skills": results}


@router.post("/skills/reload")
async def reload_skills():
    """重新加载 skill 文件，返回加载结果。"""
    loader = ds._skill_loader
    if loader is None:
        return {"status": "error", "message": "loader not initialized"}
    loader.reload()
    return {"status": "ok", "skills": len(loader._cache)}

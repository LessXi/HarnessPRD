# 设计：E2E 全链路验证 Bug 修复

## Bug #1：SkillEngine 未初始化

**根因**：`main.py` 同时使用了 `lifespan` 参数（line 79）和 `@app.on_event("startup")` 装饰器（line 125）。FastAPI 中，当 `lifespan` 被设置时，`on_event` 回调被完全忽略，导致 `init_skill_engine("skills")` 从未被调用。

**修复方案**：将 `init_skill_engine` 调用从独立的 `@app.on_event("startup")` 函数移到已有的 `lifespan` 异步上下文管理器中。

```python
# Before (main.py:68-73, 125-131)
@asynccontextmanager
async def lifespan(app: FastAPI):
    await validate_debug_config()
    yield

@app.on_event("startup")  # ← 被 lifespan 压制，从不执行
async def startup():
    from services.document_service import init_skill_engine
    init_skill_engine("skills")

# After
@asynccontextmanager
async def lifespan(app: FastAPI):
    await validate_debug_config()
    from services.document_service import init_skill_engine
    init_skill_engine("skills")
    logger.bind(event="startup").info("Skill engine initialized from backend/skills")
    yield
```

移除废弃的 `@app.on_event("startup")` 函数和未使用的 `import os`。

## Bug #2：表单验证缺失

**根因**：表单"下一步 →"按钮的点击处理函数没有验证逻辑，直接更新 viewState 到 `ai_dialogue`。

**修复方案**：在 `handleNextStep` / 表单提交函数中添加必填字段校验。11 个必填字段：
- `product_name`、`one_liner`、`problem`、`target_users`
- `mvp_features`（至少 3 项非空）
- `platform`、`needs_auth`、`needs_storage`、`page_count`

验证失败时：
1. 高亮未填写的必填字段（红色边框 + 错误提示文字）
2. 阻止 viewState 跳转
3. 不调用 localStorage 更新

## Bug #3：摘要结果未展示

**根因**：`handleGenerateSummary` 调用 API 成功后，未将返回的 summary 数据写入 UI 状态（`requirements_summary` 字段已更新但未在聊天区渲染）。

**修复方案**：在聊天消息列表中插入摘要消息（`role: "assistant"`，带特殊标记区分普通消息），或将摘要结果显示在聊天区顶部的固定区域。

推荐方案：将摘要作为一条特殊的 assistant 消息插入消息列表，带 `type: "summary"` 标记以区别于普通对话。

## 非目标

- 不改动 Skill Engine 内部逻辑
- 不改动文档生成的 review→rewrite 循环
- 不新增 UI 组件或路由

# 提案：E2E 全链路验证 Bug 修复

## Why

端到端全链路验证发现 3 个 Bug，阻断核心用户流程：

1. **SkillEngine 未初始化** — 文档生成（PRD/接口文档/提示词）全部失败，用户无法进入生成阶段
2. **表单验证缺失** — 空表单可直接跳转 AI 对话，必填字段无校验，导致后续生成的文档基于空数据
3. **摘要结果显示缺失** — 摘要 API 正常返回但 UI 不展示结果，用户无法确认需求理解

这 3 个 Bug 导致产品核心价值链路（表单 → 对话 → 文档生成 → 完成）断裂，必须立即修复。

## What Changes

- **Bug #1 修复**：将 `init_skill_engine()` 从 `@app.on_event("startup")` 迁移到 `lifespan` 函数中，确保 FastAPI 使用 lifespan 管理器时 SkillEngine 能被正确初始化
- **Bug #2 修复**：在表单提交逻辑中添加必填字段验证（11 个必填字段），未通过验证时阻止跳转并显示错误提示
- **Bug #3 修复**：在聊天界面中正确展示摘要生成结果，确保 `generateSummary` 返回后更新 UI 状态

## Capabilities

### New Capabilities

无新增 capability。

### Modified Capabilities

无 spec 级别变更。所有修复均为现有功能的 Bug 修复，不改变验收场景。

## Impact

- **后端**：`backend/main.py` — 修改 lifespan 函数，添加 `init_skill_engine` 调用
- **前端**：表单组件 — 添加必填字段验证逻辑
- **前端**：聊天组件 — 修复摘要展示逻辑

## 非目标

- 不新增表单字段或修改表单结构
- 不修改 Skill Engine 架构
- 不添加新的 API 端点
- 不修改 SSE 流式传输机制

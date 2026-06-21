# Brainstorm Summary

- Change: schema-first-form-pipeline
- Date: 2026-06-22

## 确认的技术方案

**Schema 层**：`product_schema.json` 基于 JSON Schema Draft-07，以 `x-ui` 扩展承载 UI 元数据，`x-meta.schema_version` 驱动版本迁移。放于 `backend/core/`，前端通过 Vite import 直接消费。

**后端**：`FormData` Pydantic 模型运行时动态构建（从 JSON Schema 映射），替代 `_build_form_data_model()`。API 层 4 个 Request 模型 `form_data` 从 `dict[str, Any]` → `FormData`（BREAKING）。`_validate_form()` 标记 deprecated。`prompt_validator.py` 启动时扫描 Jinja2/Skill 模板字段引用。

**前端**：ajv 消费 JSON Schema，onChange 实时校验替代手写 `validate()`。JsonPreviewModal 使用 Monaco Editor readOnly 模式 + `deltaDecorations()` 标注校验错误。预览与提交解耦（双按钮）。TypeScript `FormData` 接口手动维护（17 字段）。localStorage `_schema_version` + `migrateFormData()`。

**Debug 埋点**：前端 `debugLogger.log()` 覆盖 Schema 加载、ajv 校验、Modal 打开/关闭、迁移执行、422 捕获。后端 `logger.bind(event=...).warning/debug` 覆盖 Schema 加载、Pydantic 校验失败、Prompt 字段 warn。

**测试**：P0 后端单元 3 文件（FormData/field_registry/prompt_validator），P0 前端单元 2 文件（validation/migration），P1 E2E 3 场景，P0 一致性验证 1 项。

## 关键取舍与风险

| 取舍 | 风险 | 缓解 |
|------|------|------|
| FormData 运行时动态构建 | Schema 语法错误 → 启动崩溃 | 降级到 questions_config.json |
| `form_data: dict` → `FormData` (BREAKING) | 旧前端发弱类型 → 422 | 前端先部署 ajv 校验 |
| Monaco Editor (~2MB) | 包体积增大 | readOnly + 按需加载 |
| 手动 TS 类型 | Schema/TS 不同步 | prompt_validator 兜底检测 |

## 测试策略

- P0 后端单元 (pytest): test_form_data_model.py, test_field_registry.py, test_prompt_validator.py
- P0 前端单元 (vitest): validation.test.ts, migration.test.ts
- P0 一致性: 同份非法数据 → ajv vs Pydantic 错误集合对齐
- P1 E2E (Playwright): 正常流程 + 错误流程 + 旧数据兼容

## Spec Patch

无 — delta spec 已完整覆盖 5 个 capability，brainstorming 未发现缺失场景。

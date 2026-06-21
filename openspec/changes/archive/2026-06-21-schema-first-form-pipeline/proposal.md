## Why

当前表单数据流以弱类型 `Record<string, any>` 贯穿前后端全链路 —— 前端校验手写、API 层无类型约束、用户提交前看不到数据解析结果。Schema-First 改造将 `questions_config.json` 升级为标准 JSON Schema，驱动前后端统一校验、生成类型、提供可视化预览，消除类型不安全带来的隐性 bug 和维护成本。

## What Changes

- **BREAKING**: `backend/api/schemas.py` 中 `ChatRequest`、`SummaryRequest`、`DocumentRequest`、`OptimizeRequest` 的 `form_data` 字段从 `dict[str, Any]` 改为 Pydantic `FormData` 强类型模型
- 新增 `product_schema.json`（JSON Schema 格式），替代 `questions_config.json` 作为表单字段的单一事实来源
- 前端校验逻辑从手写 `validate()` 替换为 ajv 消费 JSON Schema
- 新增 JSON 预览 Modal：填表 → 点击预览按钮 → 弹出结构化 JSON + 校验错误高亮
- 前端 TypeScript 类型从 JSON Schema 生成（`FormData` 接口替代 `Record<string, any>`）
- localStorage `form_data` 加 `schema_version` 字段，加载时自动迁移
- Prompt 模板（Chat + Skill）启动时校验引用的字段名是否在 Schema 中存在

## Capabilities

### New Capabilities

- `form-schema`: JSON Schema 作为表单数据的单一事实来源，驱动前后端行为
- `form-validation`: Schema 驱动的前端实时校验 + API 层 Pydantic 强校验（422 兜底）
- `form-preview`: 分步 JSON 预览 Modal，展示结构化表单数据及校验错误
- `api-typed-form`: API 边界用 Pydantic `FormData` 模型强校验，替换 `dict[str, Any]`
- `typed-form-state`: 从 Schema 生成 TypeScript 类型 + localStorage 版本化迁移

### Modified Capabilities

（无 — 本次为全新 capability 引入，不修改已有 spec）

## Impact

- **前端**: `FormStep.tsx`（校验逻辑重写）、`types/index.ts`（类型替换）、新增 `JsonPreviewModal` 组件、`localStorage` 读写逻辑
- **后端**: `api/schemas.py`（Request 模型改强类型）、`core/state.py`（FormData 模型调整）、`core/questions_config.json`（重构为 JSON Schema）、`api/conversation.py` / `api/documents.py`（API 端点适配）、各 Prompt 模板（字段引用校验）
- **依赖新增**: `ajv`（前端 JSON Schema 校验）、`@monaco-editor/react` + `monaco-editor`（JSON 语法高亮预览）
- **无新增**: 数据库、认证、Redis、Docker

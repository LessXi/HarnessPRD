# Comet Design Handoff

- Change: schema-first-form-pipeline
- Phase: design
- Mode: compact
- Context hash: e966c272407da2778b0e46878e0ece642e781f553547c3d87f844f3718aff673

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/schema-first-form-pipeline/proposal.md

- Source: openspec/changes/schema-first-form-pipeline/proposal.md
- Lines: 1-34
- SHA256: 4221e2d99de3fa0c2aaa11e7e4059de2299c6eb49afdbb078308e1d371117695

```md
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
```

## openspec/changes/schema-first-form-pipeline/design.md

- Source: openspec/changes/schema-first-form-pipeline/design.md
- Lines: 1-189
- SHA256: 18c1da1769613296d93cf43c6d71f70eaa08c4b7acc93f097d37ffa448f43f4f

[TRUNCATED]

```md
## Context

当前 `questions_config.json` 为自定义 DSL，定义 17 个表单字段（11 基础 + 6 高级）。前端 `FormStep.tsx` 按 `type` 分派渲染控件（text/textarea/select/radio/list），但校验逻辑为手写 `validate()` 函数。后端 `FormData` Pydantic 模型虽通过 `_build_form_data_model()` 动态构建，但 API 层 4 个 Request 模型均以 `form_data: dict[str, Any]` 接收，校验未生效。

改造目标：以标准 JSON Schema 为单一事实来源，驱动前后端校验、类型生成、预览面板。

## Goals / Non-Goals

**Goals:**
- `product_schema.json`（JSON Schema）替代 `questions_config.json`
- 前端 ajv 消费 Schema 做实时校验，替代手写 `validate()`
- 新增分步 JSON 预览 Modal（填表 → 按钮 → 弹出）
- API 层 `form_data` 从 `dict[str, Any]` → Pydantic `FormData` 强类型
- 从 JSON Schema 生成 TypeScript `FormData` 接口
- localStorage `form_data` 加 `schema_version` + 迁移
- Prompt 模板字段引用启动时校验

**Non-Goals:**
- 对话澄清交互改动
- Skill Engine 生成流程改动
- `ProjectState` 全量类型化
- CI 阻断式静态检查

## Decisions

### 1. Schema 文件位置：`backend/core/product_schema.json`

**选择**：放在 `backend/core/`，与现有 `questions_config.json` 同目录。

**理由**：
- 与现有 `field_registry.py` 加载路径一致，后端改动最小
- 前端通过 Vite `import` 直接读取 JSON 文件（Vite 支持 JSON 导入），无需额外 API
- 避免引入 `shared/` 目录打破现有两层结构

**备选**：`shared/schemas/` 共享目录 — 更规范但引入新目录层，对当前 2 人项目过度设计。

### 2. Schema 结构设计：JSON Schema + 自定义 UI 扩展

**选择**：标准 JSON Schema Draft-07，附加 `x-ui` 自定义属性承载 UI 元数据。

```json
{
  "$schema": "https://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "product_name": {
      "type": "string",
      "minLength": 1,
      "x-ui": {
        "label": "产品名称",
        "widget": "text",
        "description": "给产品起一个简洁有辨识度的名称",
        "question": "你的产品叫什么名字？",
        "group": "base",
        "required": true
      }
    },
    "mvp_features": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 3,
      "x-ui": {
        "label": "MVP 核心功能",
        "widget": "list",
        "description": "至少列出 3 条",
        "group": "base",
        "required": true
      }
    },
    "platform_type": {
      "type": "string",
      "enum": ["web", "mobile", "wechat_miniprogram", "desktop", "multi"],
      "x-ui": {
        "label": "目标平台",
        "widget": "select",
        "group": "base",
        "required": true
      }
    }
  },
```

Full source: openspec/changes/schema-first-form-pipeline/design.md

## openspec/changes/schema-first-form-pipeline/tasks.md

- Source: openspec/changes/schema-first-form-pipeline/tasks.md
- Lines: 1-62
- SHA256: 15be36b87abc5c3fe9a2ea26656a153004cff83d6821fe020d41db1608d78305

```md
## 1. Schema 定义与后端适配（P0）

- [ ] 1.1 创建 `product_schema.json`：将 `questions_config.json` 17 个字段转为 JSON Schema Draft-07 格式，添加 `x-ui` 元数据，定义 `x-meta.schema_version`
- [ ] 1.2 重构 `field_registry.py`：优先读取 `product_schema.json`，降级读 `questions_config.json`；新增 `get_schema()` 返回完整 Schema 对象；Schema 加载成功/失败时通过 logger.bind(event=...) 记录
- [ ] 1.3 重构 `state.py` `_build_form_data_model()`：从 `product_schema.json` 构建 `FormData` Pydantic 模型，支持 JSON Schema 约束（type/enum/minLength/minItems）
- [ ] 1.4 改造 `api/schemas.py` 4 个 Request 模型：`ChatRequest`、`SummaryRequest`、`DocumentRequest`、`OptimizeRequest` 的 `form_data` 字段从 `dict[str, Any]` → `FormData`；Pydantic 校验失败（422）时 logger.bind(event="validation_failed").warning() 记录详情
- [ ] 1.5 适配 `conversation_service.py`：`chat_stream()` 和 `generate_summary()` 的 `form_data` 参数类型适配 `FormData`；`_form_to_kwargs()` 改为接收强类型对象
- [ ] 1.6 标记 `session_service._validate_form()` 为 deprecated，验证 API 层 Pydantic 校验已覆盖其职责
- [ ] 1.7 后端单元测试 — `test_form_data_model.py`：验证 `FormData` 模型正确拒绝不合法 form_data（缺必填/枚举越界/数组不足），正确接受合法数据；验证 `_validate_form()` 已标记 deprecated 且不被调用
- [ ] 1.8 后端单元测试 — `test_field_registry.py`：验证 `get_schema()` 返回有效 dict；验证 Schema 不存在时降级读 `questions_config.json` + WARNING
- [ ] 1.9 后端单元测试 — `test_prompt_validator.py`：验证合法字段引用返回空列表；验证非法字段引用返回错误列表；验证白名单字段被跳过

## 2. 前端校验迁移（P0）

- [ ] 2.1 安装 ajv 依赖，配置全局 ajv 实例，加载 `product_schema.json`
- [ ] 2.2 创建 `src/utils/validation.ts`：封装 `validateFormData(data, schema)` 返回 `{ valid, errors }`，每个 error 含字段路径和消息；每次调用通过 `debugLogger.log()` 上报校验摘要（valid/errorCount/firstError）
- [ ] 2.3 重写 `FormStep.tsx` 校验逻辑：废除手写 `validate()`，改用 ajv 驱动，实时 onChange 校验，错误绑定到对应字段
- [ ] 2.4 `FormStep.tsx` 提交按钮 disabled 逻辑：存在 ajv 错误时按钮灰显
- [ ] 2.5 前端单元测试（P0）：验证校验函数对各类非法输入的拒绝行为（缺必填/枚举越界/数组不足/全合法）

## 3. JSON 预览 Modal（P0）

- [ ] 3.1 安装 `@monaco-editor/react` + `monaco-editor` 依赖；创建 `JsonPreviewModal` 组件：接收 `formData`、`schema`、`errors` props，以 Modal 弹出
- [ ] 3.2 JSON 语法高亮渲染：使用 `@monaco-editor/react` 加载 Monaco Editor（readOnly 模式），配置 JSON language、行号、minimap 关闭；通过 `editor.deltaDecorations()` 标注校验错误行（红色波浪线 + hover message）
- [ ] 3.3 校验错误映射：将 ajv `errors` 数组转换为 Monaco `IModelDeltaDecoration[]`（字段路径 → 行号定位 → 红色波浪线 className + hoverMessage）
- [ ] 3.4 `_schema_version` 显示：JSON 底部或 Modal footer 展示版本号
- [ ] 3.5 Modal 交互：仅「关闭」按钮和遮罩点击关闭，不包含提交功能（预览与提交解耦）；打开/关闭时通过 `debugLogger.log()` 上报事件（含 fieldCount、errorCount）
- [ ] 3.6 `FormStep.tsx` 集成：表单底部「预览 JSON」按钮（表单有数据时可见，点击打开 Modal）+ 独立「提交并开始 AI 对话」按钮
- [ ] 3.7 `FormStep.tsx` 提交流程：「提交并开始 AI 对话」按钮点击 → ajv 校验 → 通过则调 `onSubmit` → 失败则表单内显示错误
- [ ] 3.8 422 兜底处理：`api.ts` 流式调用中 catch 422，解析错误详情，set 入 error 状态传给 Modal

## 4. TypeScript 类型生成与状态类型化（P1）

- [ ] 4.1 定义 `FormData` TypeScript 接口：基于 `product_schema.json` 手动定义 17 个字段的强类型接口
- [ ] 4.2 替换 `types/index.ts` 中 `ProjectState.form_data`：`Record<string, any>` → `FormData`
- [ ] 4.3 替换 `types/index.ts` 中 `ChatRequest`、`SummaryRequest`、`DocumentRequest`、`OptimizeRequest` 的 `form_data` 类型
- [ ] 4.4 级联修复：所有引用 `form_data` 的组件和函数适配 `FormData` 类型（`App.tsx`、`api.ts`、`FormStep.tsx` 等）

## 5. localStorage 版本化迁移（P1）

- [ ] 5.1 `FormData` 接口中加 `_schema_version: string` 字段
- [ ] 5.2 创建 `src/utils/migration.ts`：`migrateFormData(data: Record<string, any>)` 函数，检测版本，补默认值；迁移执行和降级时通过 `debugLogger.log()` 上报
- [ ] 5.3 创建 `src/utils/__tests__/migration.test.ts`：验证无版本补默认、同版本不变、异常降级默认
- [ ] 5.4 `App.tsx` 或 `useProjectState` hook 中加载 localStorage 时调用 `migrateFormData`
- [ ] 5.5 迁移失败兜底：try-catch，失败时用 Schema 默认值重建空 formData

## 6. Prompt 模板字段校验（P1）

- [ ] 6.1 创建 `backend/core/prompt_validator.py`：加载 Schema 获取合法字段集合，扫描模板中 `{{ field_name }}` 引用
- [ ] 6.2 定义上下文变量白名单（`form_fields`、`chat_log`、`requirements_summary`、`current_content`、`prd_content`、`api_content`、`previous_content`、`session_id`、`doc_type`）
- [ ] 6.3 `main.py` 启动时调用 `prompt_validator.validate_all()`：遍历 `backend/prompts/*.jinja2` 和 `backend/skills/*.md`，对非法引用 emit WARNING
- [ ] 6.4 修复现有模板中可能存在的字段名拼写错误（如有）

## 7. 联调测试与清理（P0）

- [ ] 7.1 后端启动验证：`FormData` 正常加载，Prompt 校验 warn 为零
- [ ] 7.2 前端启动验证：ajv 加载 Schema 成功，表单渲染正常
- [ ] 7.3 E2E 正常流程（P1）：填写表单 → ajv 实时校验 → 预览 Modal（Monaco 渲染正确）→ 校验通过 → 提交 → 后端 200 → 进入对话
- [ ] 7.4 E2E 错误流程（P1）：缺必填字段 → 预览 Modal 红字 decoration → 提交按钮禁用；后端 422 场景模拟
- [ ] 7.5 E2E 旧数据兼容（P1）：注入无 `_schema_version` 的 localStorage 数据，刷新页面确认正常迁移
- [ ] 7.6 前后端校验一致性：同一份非法 form_data 分别经 ajv 和 Pydantic 校验，错误字段集合一致
- [ ] 7.7 更新 `docs/form-data-structure.md`：反映 Schema 变更，标注 `questions_config.json` deprecated
```

## openspec/changes/schema-first-form-pipeline/specs/api-typed-form/spec.md

- Source: openspec/changes/schema-first-form-pipeline/specs/api-typed-form/spec.md
- Lines: 1-38
- SHA256: ef7c8db7bdff171b3815d79b7ff47dd3ca0d8c341db096335c7b842dcbc41a17

```md
## ADDED Requirements

### Requirement: Strong-typed form_data at API boundary
后端 4 个 API 请求模型（`ChatRequest`、`SummaryRequest`、`DocumentRequest`、`OptimizeRequest`）的 `form_data` 字段 SHALL 从 `dict[str, Any]` 改为 Pydantic `FormData` 强类型模型。

#### Scenario: ChatRequest uses FormData model
- **WHEN** POST /api/chat/stream 收到请求
- **THEN** FastAPI 自动将 `form_data` 校验为 `FormData` 实例，类型不匹配返回 422

#### Scenario: SummaryRequest uses FormData model
- **WHEN** POST /api/summary/generate 收到请求
- **THEN** `form_data` 经 Pydantic `FormData` 校验后传入服务层

#### Scenario: DocumentRequest uses FormData model
- **WHEN** POST /api/documents/{type}/stream 收到请求
- **THEN** `form_data` 经 Pydantic `FormData` 校验后传入 Skill Engine

#### Scenario: OptimizeRequest uses FormData model
- **WHEN** POST /api/documents/{type}/optimize 收到请求
- **THEN** `form_data` 经 Pydantic `FormData` 校验后传入 Skill Engine

### Requirement: FormData model built from product_schema.json
`FormData` Pydantic 模型 SHALL 从 `product_schema.json` 动态构建，而非手写字段定义。

#### Scenario: Schema change automatically reflects in FormData
- **WHEN** `product_schema.json` 中新增一个必填字段
- **THEN** 重启后端后 `FormData` 模型自动包含该字段的校验规则，无需修改 Python 代码

#### Scenario: Legacy questions_config.json fallback
- **WHEN** `product_schema.json` 不可用但 `questions_config.json` 存在
- **THEN** `FormData` 回退到旧构建逻辑（`_build_form_data_model()`），emit WARNING

### Requirement: Deprecated manual _validate_form
`session_service._validate_form()` SHALL 标记为 deprecated，其职责由 API 层 Pydantic 校验取代。

#### Scenario: Manual validation no longer invoked
- **WHEN** API 层已使用 `FormData` 强类型校验
- **THEN** 服务层不再调用 `_validate_form()`，改由 API 边界保障数据合法性
```

## openspec/changes/schema-first-form-pipeline/specs/form-preview/spec.md

- Source: openspec/changes/schema-first-form-pipeline/specs/form-preview/spec.md
- Lines: 1-53
- SHA256: 40f6174b96917c10f12a94f47009ee575b3e453445254c83459945d04f4916b9

```md
## ADDED Requirements

### Requirement: Step-based JSON preview modal
系统 SHALL 提供分步 JSON 预览功能：用户在表单页点击「预览 JSON」按钮 → 弹出 Modal 展示当前表单数据的结构化 JSON。

#### Scenario: Preview button visible when form has data
- **WHEN** 用户在表单页已填写至少一个字段
- **THEN** 页面底部显示「预览 JSON」按钮

#### Scenario: Modal displays structured JSON
- **WHEN** 用户点击「预览 JSON」按钮
- **THEN** 弹出 Modal，以语法高亮的 JSON 格式展示当前表单数据，包含 `_schema_version` 字段

#### Scenario: Modal shows validation errors highlighted in JSON
- **WHEN** 当前表单数据存在校验错误
- **THEN** Modal 中 JSON 对应字段行以红色高亮，行尾/悬浮 tooltip 显示错误原因

#### Scenario: Modal shows success state when all valid
- **WHEN** 当前表单数据全部字段校验通过
- **THEN** Modal 中 JSON 以正常样式展示，底部「确认提交」按钮为可用状态

#### Scenario: Modal close returns to form
- **WHEN** 用户在 Modal 中点击「关闭」或 Modal 外部遮罩
- **THEN** Modal 关闭，回到表单页，已填写数据保持不变

#### Scenario: Preview and submit are decoupled
- **WHEN** 用户在 Modal 中查看 JSON 预览和校验错误
- **THEN** Modal 中不包含「确认提交」按钮，提交操作由表单页的独立「提交并开始 AI 对话」按钮完成

### Requirement: JSON syntax highlighting
Modal 中的 JSON 展示 SHALL 使用语法高亮，使用户可读性。

#### Scenario: Different token types have distinct colors
- **WHEN** Modal 显示 JSON 数据
- **THEN** 键名、字符串值、数组、布尔值以不同颜色渲染

### Requirement: Schema version display in preview
Modal SHALL 在 JSON 内容区域或底部显示当前 `_schema_version`。

#### Scenario: Schema version visible in preview
- **WHEN** 用户打开 JSON 预览 Modal
- **THEN** JSON 数据中或 Modal 底部可见 `_schema_version: "1.0.0"`

### Requirement: Preview modal debug instrumentation
预览 Modal 的打开/关闭 SHALL 通过 debug 系统记录。

#### Scenario: Modal open logged
- **WHEN** 用户点击「预览 JSON」按钮打开 Modal
- **THEN** `debugLogger.log('info', 'preview:modal', { action: 'open', fieldCount, errorCount })` 上报

#### Scenario: Modal close logged
- **WHEN** 用户关闭预览 Modal
- **THEN** `debugLogger.log('info', 'preview:modal', { action: 'close' })` 上报
```

## openspec/changes/schema-first-form-pipeline/specs/form-schema/spec.md

- Source: openspec/changes/schema-first-form-pipeline/specs/form-schema/spec.md
- Lines: 1-52
- SHA256: b0db3bbe92f05da34b09f68b28f8bffde90806299b7e34ddaa00b504bec29c04

```md
## ADDED Requirements

### Requirement: JSON Schema as single source of truth
系统 SHALL 使用标准 JSON Schema Draft-07 格式的 `product_schema.json` 作为表单数据的单一事实来源，定义所有字段的类型、约束及 UI 元数据。

#### Scenario: Schema defines all form fields
- **WHEN** 读取 `product_schema.json` 的 `properties` 节点
- **THEN** 包含全部 17 个表单字段（11 基础 + 6 高级），每个字段含标准 JSON Schema 关键字（type, enum, minLength, minItems）和 `x-ui` 自定义 UI 元数据

#### Scenario: Schema drives frontend field rendering
- **WHEN** 前端加载 Schema 中 `x-ui.group` 为 `"base"` 的字段
- **THEN** 在基础问题区域按 Schema `properties` 顺序渲染控件
- **WHEN** 前端加载 `x-ui.group` 为 `"advanced"` 的字段
- **THEN** 在高级配置折叠区渲染

#### Scenario: Schema version is embedded
- **WHEN** 读取 `product_schema.json` 的 `x-meta.schema_version`
- **THEN** 值为语义化版本号（如 `"1.0.0"`），前后端均据此判断数据兼容性

#### Scenario: Backward compatibility with legacy config
- **WHEN** `product_schema.json` 不存在但 `questions_config.json` 存在
- **THEN** `field_registry.py` 回退读取旧格式，emit WARNING 日志

### Requirement: Schema loading debug instrumentation
Schema 加载过程 SHALL 通过 debug 系统暴露可观测性。

#### Scenario: Successful schema load logged
- **WHEN** `product_schema.json` 成功加载并解析
- **THEN** 日志记录 Schema 版本号（`x-meta.schema_version`）和字段总数

#### Scenario: Schema load failure logged and degraded
- **WHEN** `product_schema.json` 缺失或 JSON 语法错误
- **THEN** logger.bind(event="schema_load_failed").warning() 记录失败原因，降级到 `questions_config.json`

#### Scenario: Frontend schema load reported to debug backend
- **WHEN** 前端 Vite `import` 加载 `product_schema.json` 成功
- **THEN** `debugLogger.log('info', 'schema:loaded', { version, fieldCount })` 上报

### Requirement: Schema field type constraints
Schema 中每个字段的 JSON Schema 关键字 SHALL 与业务规则一致，可被 ajv 和 Pydantic 直接消费。

#### Scenario: String fields with minLength
- **WHEN** 必填字符串字段（如 `product_name`）在 Schema 中定义为 `"type": "string", "minLength": 1`
- **THEN** ajv 和 Pydantic 均校验非空

#### Scenario: Enum fields with constrained values
- **WHEN** 选择类字段（如 `platform_type`）在 Schema 中定义 `"enum": ["web", "mobile", "wechat_miniprogram", "desktop", "multi"]`
- **THEN** 不在枚举范围内的值被 ajv 和 Pydantic 拒绝

#### Scenario: Array field with minItems
- **WHEN** `mvp_features` 在 Schema 中定义为 `"type": "array", "minItems": 3`
- **THEN** 数组长度不足 3 时 ajv 和 Pydantic 均返回校验失败
```

## openspec/changes/schema-first-form-pipeline/specs/form-validation/spec.md

- Source: openspec/changes/schema-first-form-pipeline/specs/form-validation/spec.md
- Lines: 1-65
- SHA256: 0064e41f8a181ff120784a471c4627e1005977809eb3d9bd51593d7ff61159c4

```md
## ADDED Requirements

### Requirement: Frontend real-time validation via ajv
前端 SHALL 使用 ajv 库消费 `product_schema.json`，在用户输入时实时校验表单数据，替代当前手写 `validate()` 函数。

#### Scenario: Real-time validation on field change
- **WHEN** 用户在必填字段输入框清空内容（onChange 触发）
- **THEN** 该字段下方立即显示红色错误提示「<label>为必填项」

#### Scenario: Array field minimum items validation
- **WHEN** `mvp_features` 数组长度不足 3
- **THEN** 该字段区域显示错误提示「至少需要 3 项，且每项不能为空」

#### Scenario: Enum field value validation
- **WHEN** 选择/单选字段的值不在 Schema `enum` 列表中
- **THEN** 该字段显示错误提示「值不在允许范围内」

#### Scenario: Valid field clears error
- **WHEN** 用户修正了触发校验错误的字段
- **THEN** ajv 再次校验通过，对应错误提示消失

#### Scenario: Submit button disabled on errors
- **WHEN** 存在任何校验错误（`ajv.validate()` 返回 false）
- **THEN** 提交按钮处于 disabled 状态，不可点击

### Requirement: Backend Pydantic validation at API boundary
后端 SHALL 在 API 层使用 Pydantic `FormData` 模型校验 `form_data`，不合法请求返回 HTTP 422 Unprocessable Entity。

#### Scenario: Missing required field returns 422
- **WHEN** 前端发送的 `form_data` 缺少必填字段（如 `product_name`）
- **THEN** 后端返回 HTTP 422，响应体包含缺失字段路径

#### Scenario: Invalid enum value returns 422
- **WHEN** `platform_type` 值为不在 Schema 定义枚举中的字符串
- **THEN** 后端返回 HTTP 422，响应体指出不合法的字段和值

#### Scenario: Valid form_data passes validation
- **WHEN** `form_data` 包含所有必填字段、枚举值合法、`mvp_features` 长度 ≥ 3
- **THEN** Pydantic 校验通过，请求正常进入服务层

#### Scenario: Frontend catches 422 as fallback
- **WHEN** 前端收到后端 422 响应（兜底场景）
- **THEN** JSON 预览 Modal 中显示后端返回的具体校验错误信息

### Requirement: Validation consistency between frontend and backend
前后端对同一 Schema 的校验结果 SHALL 保持一致。

#### Scenario: Same Schema yields same validation result
- **WHEN** 同一份 form_data 分别经过 ajv（前端）和 Pydantic（后端）校验
- **THEN** 两者的通过/失败结论一致，错误字段集合一致

### Requirement: Validation debug instrumentation
前后端校验过程 SHALL 通过 debug 系统暴露可观测性。

#### Scenario: ajv validation result logged
- **WHEN** 前端 `ajv.validate()` 返回结果
- **THEN** `debugLogger.log('info', 'validation:ajv', { valid, errorCount, firstError })` 上报校验摘要

#### Scenario: Pydantic validation failure logged
- **WHEN** 后端 Pydantic `FormData` 校验失败（HTTP 422）
- **THEN** logger.bind(event="validation_failed").warning() 记录失败字段路径、值和约束

#### Scenario: Frontend reports 422 details to debug backend
- **WHEN** 前端 `api.ts` 捕获后端 422 响应
- **THEN** `debugLogger.log('warn', 'validation:422', { errors: [...] })` 上报后端校验错误详情
```

## openspec/changes/schema-first-form-pipeline/specs/typed-form-state/spec.md

- Source: openspec/changes/schema-first-form-pipeline/specs/typed-form-state/spec.md
- Lines: 1-57
- SHA256: 38f15326faebea369c643a65f03b6df568aa89bf0d5697857bfa3e717c333604

```md
## ADDED Requirements

### Requirement: TypeScript FormData type generated from Schema
前端 SHALL 定义与 `product_schema.json` 字段一致的 TypeScript `FormData` 接口，替代各处的 `Record<string, any>`。

#### Scenario: FormData interface includes all schema fields
- **WHEN** 检查 TypeScript `FormData` 接口定义
- **THEN** 包含所有 17 个字段，类型与 Schema 一致（string / string[]），可选字段标记 `?`

#### Scenario: ProjectState.form_data uses FormData type
- **WHEN** `ProjectState` 接口中 `form_data` 字段
- **THEN** 类型为 `FormData` 而非 `Record<string, any>`

#### Scenario: API request types use FormData
- **WHEN** `ChatRequest`、`SummaryRequest`、`DocumentRequest`、`OptimizeRequest` 接口中 `form_data` 字段
- **THEN** 类型为 `FormData` 而非 `Record<string, any>`

### Requirement: localStorage schema versioning and migration
前端 SHALL 在存储的 `form_data` 中嵌入 `_schema_version` 字段，加载时检测版本差异并自动迁移。

#### Scenario: Fresh data includes schema version
- **WHEN** 用户首次填写表单
- **THEN** `form_data` 中包含 `_schema_version: "1.0.0"`

#### Scenario: Legacy data without version auto-migrates
- **WHEN** localStorage 中存在无 `_schema_version` 的旧 form_data
- **THEN** 加载时自动补全缺失的选填字段默认值，添加 `_schema_version: "1.0.0"`

#### Scenario: Migration failure falls back to defaults
- **WHEN** 迁移过程抛出异常（数据损坏）
- **THEN** catch 异常，使用 Schema 默认值重建 form_data，不阻断页面渲染

### Requirement: Prompt template field reference validation on startup
后端启动时 SHALL 校验 Chat Prompt 模板和 Skill 模板中引用的表单字段名是否在 `product_schema.json` 中存在。

#### Scenario: Unknown field reference emits warning
- **WHEN** 模板中包含 `{{ nonexistent_field }}` 引用
- **THEN** 启动时输出 WARNING 日志，列出文件名和不存在的字段名

#### Scenario: All valid field references pass silently
- **WHEN** 模板中所有 `{{ field_name }}` 引用均在 Schema `properties` 中存在（或属于上下文白名单）
- **THEN** 启动时不产生 WARNING

#### Scenario: Context variables excluded from check
- **WHEN** 模板中包含 `{{ form_fields }}`、`{{ chat_log }}`、`{{ requirements_summary }}` 等上下文变量
- **THEN** 这些变量名不在 Schema 校验范围内，不触发误报

### Requirement: Migration debug instrumentation
localStorage 数据迁移过程 SHALL 通过 debug 系统记录。

#### Scenario: Migration executed logged
- **WHEN** `migrateFormData()` 检测到版本差异并执行迁移
- **THEN** `debugLogger.log('info', 'migration:executed', { fromVersion, toVersion, addedDefaults: [...] })` 上报

#### Scenario: Migration fallback logged
- **WHEN** 迁移过程异常导致降级到默认值
- **THEN** `debugLogger.log('error', 'migration:fallback', { error })` 上报
```


# typed-form-state Specification

## Purpose
TBD - created by archiving change schema-first-form-pipeline. Update Purpose after archive.
## Requirements
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


# api-typed-form Specification

## Purpose
TBD - created by archiving change schema-first-form-pipeline. Update Purpose after archive.
## Requirements
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


# form-schema Specification

## Purpose
TBD - created by archiving change schema-first-form-pipeline. Update Purpose after archive.
## Requirements
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


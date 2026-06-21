# form-validation Specification

## Purpose
TBD - created by archiving change schema-first-form-pipeline. Update Purpose after archive.
## Requirements
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


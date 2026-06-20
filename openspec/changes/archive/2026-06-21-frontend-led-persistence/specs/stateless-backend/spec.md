## ADDED Requirements

### Requirement: 后端无状态 API

后端 SHALL 不存储任何会话状态。所有 API 端点 MUST 从请求体中获取完整上下文。

#### Scenario: 请求携带完整上下文

- **WHEN** 前端调用任何 API 端点
- **THEN** 请求体包含该端点所需的全部数据（form_data、history、documents 等），后端不查询任何内存或文件存储

#### Scenario: 服务器重启无影响

- **WHEN** 后端服务器重启
- **THEN** 所有 API 端点正常工作，因为后端不依赖任何持久状态

### Requirement: session_id 透传日志

后端 SHALL 接受请求体中的 session_id 字段，仅用于日志追踪，不校验是否存在。

#### Scenario: session_id 日志记录

- **WHEN** 后端处理请求
- **THEN** 在日志中记录 session_id，用于关联同一项目的多个请求

#### Scenario: session_id 缺失

- **WHEN** 请求体中 session_id 为空或缺失
- **THEN** 后端正常处理请求，日志中标记 session_id 为 unknown

### Requirement: 对话 API 端点

后端 SHALL 提供 `POST /api/chat/stream` 端点，接受完整对话历史，返回 SSE 流式 AI 回复。

#### Scenario: 对话请求

- **WHEN** 前端发送 `POST /api/chat/stream`，请求体包含 `session_id`、`history`（ChatMessage[]）、`form_data`
- **THEN** 后端用 history 构建 LangChain 消息列表，调用 LLM，SSE 流式返回 AI 回复

#### Scenario: 首次对话（破冰）

- **WHEN** history 为空数组
- **THEN** 后端使用 chat_system.jinja2 模板，基于 form_data 生成破冰问候

#### Scenario: 接续对话

- **WHEN** history 包含之前的对话
- **THEN** 后端将 history 转为 LangChain 消息，追加到 system prompt 后，调用 LLM

### Requirement: 文档生成 API 端点

后端 SHALL 提供 `POST /api/documents/{type}/stream` 端点，接受项目上下文，返回 SSE 流式文档内容。

#### Scenario: PRD 生成

- **WHEN** 前端发送 `POST /api/documents/prd/stream`，请求体包含 `session_id`、`form_data`、`requirements_summary`
- **THEN** 后端加载 generate_prd.jinja2 模板，渲染上下文，SSE 流式返回 PRD 内容

#### Scenario: 接口文档生成

- **WHEN** 前端发送 `POST /api/documents/api/stream`，请求体包含 `session_id`、`form_data`、`requirements_summary`、`prd_content`
- **THEN** 后端加载 generate_api.jinja2 模板，SSE 流式返回接口文档

#### Scenario: 提示词套件生成

- **WHEN** 前端发送 `POST /api/documents/prompts/stream`，请求体包含 `session_id`、`form_data`、`requirements_summary`、`prd_content`、`api_content`
- **THEN** 后端加载 generate_prompts.jinja2 模板，SSE 流式返回提示词套件

### Requirement: 文档优化 API 端点

后端 SHALL 提供 `POST /api/documents/{type}/optimize` 端点，执行 review→rewrite 循环，SSE 流式返回最终优化结果。

#### Scenario: 优化请求

- **WHEN** 前端发送 `POST /api/documents/{type}/optimize`，请求体包含 `session_id`、`content`、`form_data`、`requirements_summary` 及相关文档
- **THEN** 后端执行 review→rewrite 循环（最多 3 轮），SSE 流式返回最终优化后的文档内容

#### Scenario: 审核通过提前终止

- **WHEN** review 阶段判定"审核通过"
- **THEN** 后端停止循环，返回当前文档内容

#### Scenario: 达到最大轮次

- **WHEN** review→rewrite 循环达到 3 轮
- **THEN** 后端停止循环，返回最后一轮 rewrite 的结果

### Requirement: 需求摘要生成 API 端点

后端 SHALL 提供 `POST /api/summary/generate` 端点，接受对话历史和表单数据，返回结构化需求摘要。

#### Scenario: 摘要生成

- **WHEN** 前端发送 `POST /api/summary/generate`，请求体包含 `session_id`、`history`、`form_data`
- **THEN** 后端使用 chat_summary.jinja2 模板生成摘要，返回 JSON `{"summary": "..."}`

### Requirement: 表单配置 API 端点

后端 SHALL 保留 `GET /api/questions` 端点，返回表单配置 JSON。

#### Scenario: 获取表单配置

- **WHEN** 前端请求 `GET /api/questions`
- **THEN** 后端返回 questions_config.json 内容

### Requirement: 文档下载 API 端点

后端 SHALL 保留 `POST /api/documents/{type}/download` 端点。

#### Scenario: 下载文档

- **WHEN** 前端请求 `POST /api/documents/{type}/download`，请求体包含文档内容
- **THEN** 后端返回 .md 文件下载

### Requirement: 删除旧 API 端点

后端 SHALL 删除所有 `/api/sessions/*` 路由及相关代码。

#### Scenario: 旧端点不可访问

- **WHEN** 请求 `/api/sessions/*` 任意路径
- **THEN** 返回 404

#### Scenario: 删除 SessionStore

- **WHEN** 后端代码部署
- **THEN** `core/state.py` 中的 SessionStore 类和 session_store 单例已被删除

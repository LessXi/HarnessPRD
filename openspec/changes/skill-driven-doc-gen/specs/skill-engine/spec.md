# Spec: skill-engine

Skill Engine 是文档生成后端的核心模块，负责解析 `.md` skill 文件并按声明的步骤链式执行 LLM 调用。

## ADDED Requirements

### Requirement: Skill 文件解析

系统 SHALL 解析符合 Claude skill 兼容格式的 `.md` 文件（YAML frontmatter + Markdown body），并输出 Pydantic 校验后的 SkillSchema 数据结构。

YAML frontmatter 必填字段：`name`、`description`、`steps`。`steps` 中每步必填 `id`、`type`（`generate` | `review` | `rewrite`）、`prompt`。可选字段：`version`、`max_iterations`。每步可选字段：`stream`（默认 true）、`criteria`（仅 review 步）、`pass_condition`（仅 review 步）。

#### Scenario: 解析有效的 skill 文件

- **WHEN** 引擎加载格式正确的 `.md` skill 文件
- **THEN** 返回 SkillSchema 对象，包含所有字段的解析结果

#### Scenario: 解析缺少必填字段的 skill 文件

- **WHEN** skill YAML frontmatter 缺少 `steps` 字段
- **THEN** 抛出 SkillParseError，包含文件路径和缺失字段名

#### Scenario: 解析无效 YAML frontmatter

- **WHEN** skill 文件的 YAML frontmatter 格式错误（如缩进不对）
- **THEN** 抛出 SkillParseError，包含文件路径和 YAML 解析错误详情

### Requirement: Prompt 链式执行

系统 SHALL 按 skill 文件中 `steps` 声明的顺序依次执行每步，每步调用 LLM 并产出对应事件。

步骤类型：
- `generate`: 流式调用 LLM → yield SSE `chunk` 事件（逐 token）
- `review`: 非流式调用 LLM → 检查输出是否含 `pass_condition` → yield `review_result` 事件（含审核意见和通过状态）
- `rewrite`: 流式调用 LLM（输入：原文 + 审核意见） → yield SSE `chunk` 事件

每步执行前，SHALL 将上下文变量（`form_data`、`requirements_summary`、`prd_content`、`api_content` 等）通过 `{{ variable_name }}` 语法替换到 `prompt` 中。

#### Scenario: 单步 generate 执行

- **WHEN** skill 仅包含一个 `generate` 步骤，`stream: true`
- **THEN** 引擎逐 token 流式输出 `chunk` 事件，最后输出 `done` 事件，生成的完整文档内容作为 `done` 事件的 payload

#### Scenario: review→rewrite 循环通过

- **WHEN** skill 包含 `review` + `rewrite` 步骤，review 输出含 "审核通过"（满足 `pass_condition`）
- **THEN** 引擎执行 review → 判断通过 → 跳过 rewrite → 输出 `done` 事件，含当前文档内容

#### Scenario: review→rewrite 循环 1 轮后通过

- **WHEN** skill 包含 review + rewrite，第一轮 review 输出不含 "审核通过"
- **THEN** 引擎执行 review → 判断不通过 → 执行 rewrite（流式输出 chunk） → 再执行 review → 通过 → 输出 `done`

#### Scenario: review→rewrite 循环达到 max_iterations 上限

- **WHEN** skill 设置 `max_iterations: 2`，review 连续 2 轮均未通过
- **THEN** 引擎在 2 轮后终止循环，输出最后 rewrite 的内容作为 `done` 事件 payload

#### Scenario: 模板变量替换

- **WHEN** skill prompt 中包含 `{{ form_data.product_name }}`
- **THEN** 引擎在调用 LLM 前将 `{{ form_data.product_name }}` 替换为实际值

### Requirement: 热加载

系统 SHALL 支持在运行时重新加载 skill 文件目录，新请求使用新版本 skill，活跃请求继续使用加载时的版本。

#### Scenario: 启动时加载所有 skill

- **WHEN** SkillLoader 初始化时指定 `backend/skills/` 目录
- **THEN** 扫描目录下所有 `.md` 文件，解析并缓存到内存（key 为 skill name）

#### Scenario: 热加载触发

- **WHEN** 调用 `loader.reload()` 或访问 reload API 端点
- **THEN** 重新扫描目录，解析新版 skill 文件，更新缓存；旧版本保留直到所有引用释放

#### Scenario: skill 文件不存在

- **WHEN** 请求的 skill name 在缓存中不存在
- **THEN** 引擎返回 SkillNotFoundError，前端收到 error SSE 事件

### Requirement: SSE 事件格式

系统 SHALL 使用统一的 SSE 事件格式输出：

```json
{"event": "chunk", "content": "<token>"}
{"event": "done", "content": "<完整文档>"}
{"event": "error", "content": "<错误信息>"}
{"event": "review_result", "content": "<审核意见>", "passed": true/false}
```

#### Scenario: chunk 事件格式

- **WHEN** LLM 流式输出每个 token
- **THEN** 引擎包装为 `{"event": "chunk", "content": "<token>"}` 格式的 SSE 事件

#### Scenario: error 事件

- **WHEN** LLM 调用失败或 skill 解析失败
- **THEN** 引擎输出 `{"event": "error", "content": "<错误描述>"}` 并终止流

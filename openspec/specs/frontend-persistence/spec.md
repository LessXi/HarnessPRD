## ADDED Requirements

### Requirement: 项目状态持久化

前端 SHALL 将全部项目状态持久化到 localStorage 单键 `harnessprd:project`。状态包括：session_id、form_data、messages、requirements_summary、三份文档内容及确认状态、viewState。

#### Scenario: 页面刷新恢复

- **WHEN** 用户刷新页面
- **THEN** 前端从 localStorage 读取 `harnessprd:project`，恢复 viewState 和所有数据，无需后端参与

#### Scenario: 关闭重开恢复

- **WHEN** 用户关闭浏览器后重新打开
- **THEN** 前端从 localStorage 读取项目状态，恢复到上次的 viewState

#### Scenario: 首次访问无数据

- **WHEN** 用户首次访问（localStorage 无 `harnessprd:project`）
- **THEN** 前端初始化空状态，viewState 为 `form_editing`

### Requirement: 前端生成 session_id

前端 SHALL 在首次创建项目时用 `crypto.randomUUID()` 生成 session_id，并存储在项目状态中。

#### Scenario: 创建新项目

- **WHEN** 用户首次提交表单
- **THEN** 前端生成 UUID 作为 session_id，存入 localStorage，后续所有请求携带此 ID

#### Scenario: session_id 不变

- **WHEN** 用户在同一项目中进行对话、生成文档
- **THEN** session_id 保持不变，贯穿整个项目生命周期

### Requirement: 状态变更自动持久化

前端 SHALL 在每次状态变更时自动写入 localStorage。

#### Scenario: 对话消息持久化

- **WHEN** 用户发送消息或收到 AI 回复
- **THEN** messages 数组立即写入 localStorage

#### Scenario: 文档内容持久化

- **WHEN** 文档生成完成（SSE done 事件）
- **THEN** 文档内容立即写入 localStorage

#### Scenario: viewState 持久化

- **WHEN** viewState 发生变化（如从 form_editing 到 ai_dialogue）
- **THEN** 新的 viewState 立即写入 localStorage

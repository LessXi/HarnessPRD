## Requirements

### Requirement: 文档生成续写

文档生成 API SHALL 支持 `previous_content` 可选参数，用于断点续写。

#### Scenario: 正常生成（无续写）

- **WHEN** 前端发送文档生成请求，`previous_content` 为空
- **THEN** 后端从头生成完整文档，SSE 流式返回

#### Scenario: 续写请求

- **WHEN** 前端发送文档生成请求，`previous_content` 包含已生成的内容
- **THEN** 后端在 prompt 中追加续写指令，从断点处继续生成，SSE 流式返回续写内容

#### Scenario: 续写不重复已有内容

- **WHEN** 后端处理续写请求
- **THEN** prompt 中 MUST 明确指示 LLM "不要重复已有内容，从断点处继续"

### Requirement: SSE 中断检测

前端 SHALL 检测 SSE 流中断，并将已接收的部分内容保存到项目状态。

#### Scenario: 网络中断

- **WHEN** SSE 流因网络问题中断
- **THEN** 前端将已接收的 streamingContent 保存到对应文档的 content 字段

#### Scenario: 用户关闭页面

- **WHEN** 用户在文档生成过程中关闭页面
- **THEN** localStorage 中已持久化的 content 保留（通过状态自动持久化机制）

### Requirement: 续写 UI 交互

前端 SHALL 在文档生成中断后提供"继续生成"按钮。

#### Scenario: 中断后显示续写按钮

- **WHEN** 文档生成中断（SSE error 或网络断开）
- **THEN** 前端显示"继续生成"按钮，已有内容保留在页面上

#### Scenario: 点击续写

- **WHEN** 用户点击"继续生成"
- **THEN** 前端发送文档生成请求，`previous_content` 为当前已有的文档内容

#### Scenario: 续写完成

- **WHEN** 续写 SSE 流完成
- **THEN** 前端将续写内容追加到已有 content 后面

### Requirement: 续写 Prompt 模板

Jinja2 生成模板 MUST 支持 `previous_content` 参数。

#### Scenario: 模板续写分支

- **WHEN** `previous_content` 非空
- **THEN** 模板渲染续写指令，包含已有内容和"请继续"指示

#### Scenario: 模板正常分支

- **WHEN** `previous_content` 为空
- **THEN** 模板渲染完整的生成指令（与现有行为一致）

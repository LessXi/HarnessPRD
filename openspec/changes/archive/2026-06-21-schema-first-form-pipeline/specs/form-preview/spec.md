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

# stop-generation Specification

## Purpose
TBD - created by archiving change fix-buttons-and-state-flow. Update Purpose after archive.
## Requirements
### Requirement: 停止生成按钮
系统 SHALL 在 `generating_*` 状态下提供「停止生成」按钮，允许用户中断文档生成。

#### Scenario: 生成中显示停止按钮
- **WHEN** 文档正在流式生成中（viewState 为 `generating_prd` / `generating_api` / `generating_prompts`）
- **THEN** 在 DocumentReview 工具栏显示「停止生成」按钮

#### Scenario: 点击停止生成
- **WHEN** 用户点击「停止生成」按钮
- **THEN** 系统 abort 当前 SSE fetch 连接，停止接收流式数据，viewState 回退到生成前状态（如 `generating_prd` → `ai_dialogue`）

#### Scenario: 停止后保留部分内容
- **WHEN** 用户停止生成
- **THEN** 保留已接收的部分文档内容，不丢弃

#### Scenario: 停止后可重新生成
- **WHEN** 用户停止生成后
- **THEN** 用户可以再次触发生成，重新开始完整 SSE 流式过程


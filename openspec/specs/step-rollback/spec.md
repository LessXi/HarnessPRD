# step-rollback Specification

## Purpose
TBD - created by archiving change ux-optimization-flow-closure. Update Purpose after archive.
## Requirements
### Requirement: 回退到任意已完成步骤
系统 SHALL 允许用户通过统一的 `handleGoBack` 入口回退到任意已完成步骤，保留数据并标记受影响步骤为待更新。

#### Scenario: 统一回退入口
- **WHEN** 用户通过 Sidebar「上一步」按钮、点击已完成步骤、或 CompletionPromptBar「返回」按钮触发回退
- **THEN** 均调用统一的 `handleGoBack(targetState)` 函数，行为一致

#### Scenario: 回退到对话阶段
- **WHEN** 用户从审阅 PRD 阶段回退到对话阶段
- **THEN** 保留对话历史，PRD/API/提示词文档的 `confirmed` 重置为 `false`，标记为待更新

#### Scenario: 回退到 PRD 阶段
- **WHEN** 用户从审阅 API 阶段回退到 PRD 阶段
- **THEN** 保留 PRD 内容，API/提示词文档的 `confirmed` 重置为 `false`，标记为待更新

#### Scenario: 回退时 completedSteps 更新
- **WHEN** 用户确认回退到目标状态
- **THEN** `completedSteps` 移除以目标状态为界的所有后续步骤

### Requirement: 待更新状态标记
系统 SHALL 标记后续步骤为待更新状态，在UI中显示⚠图标提醒用户。

#### Scenario: 待更新状态显示
- **WHEN** 步骤被标记为待更新
- **THEN** 进度条中显示⚠图标，点击时显示"数据可能不一致"提示

#### Scenario: 待更新状态清除
- **WHEN** 用户重新生成或确认文档
- **THEN** 清除该步骤的待更新状态

### Requirement: 回退确认对话框
系统 SHALL 在回退时显示确认对话框，提示用户将发生的变化。

#### Scenario: 确认对话框内容
- **WHEN** 用户触发回退操作
- **THEN** 显示对话框，列出目标状态后所有受影响步骤及其 `confirmed` 将被重置

#### Scenario: 确认回退
- **WHEN** 用户确认回退
- **THEN** 执行回退：重置受影响步骤 `confirmed` → 添加 `pendingUpdates` → 更新 `viewState` → 调整 `completedSteps`

#### Scenario: 取消回退
- **WHEN** 用户取消回退
- **THEN** 保持当前状态不变

### Requirement: 重新生成功能
系统 SHALL 为待更新步骤提供重新生成功能。

#### Scenario: 重新生成提示
- **WHEN** 用户查看待更新步骤
- **THEN** 显示"重新生成"按钮，点击后重新生成文档

#### Scenario: 跳过重新生成
- **WHEN** 用户选择跳过重新生成
- **THEN** 继续使用现有文档内容

### Requirement: CompletionPromptBar 返回行为
系统 SHALL 使 CompletionPromptBar 的「返回」按钮也触发统一回退逻辑。

#### Scenario: 提示栏返回
- **WHEN** 用户点击 CompletionPromptBar 的「返回」按钮
- **THEN** 触发 `handleGoBack`，回退到上一个稳定状态（而非仅关闭提示栏）


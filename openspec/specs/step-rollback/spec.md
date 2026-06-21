# step-rollback Specification

## Purpose
TBD - created by archiving change ux-optimization-flow-closure. Update Purpose after archive.
## Requirements
### Requirement: 回退到任意已完成步骤
系统 SHALL 允许用户回退到任意已完成步骤，保留后续数据并标记为待更新。

#### Scenario: 回退到对话阶段
- **WHEN** 用户从审阅PRD阶段回退到对话阶段
- **THEN** 保留对话历史，标记摘要、PRD、接口文档、提示词为待更新

#### Scenario: 回退到PRD阶段
- **WHEN** 用户从审阅API阶段回退到PRD阶段
- **THEN** 保留PRD内容，标记接口文档、提示词为待更新

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
- **WHEN** 用户点击回退按钮
- **THEN** 显示对话框："返回X阶段将标记Y、Z为待更新，确定吗？"

#### Scenario: 确认回退
- **WHEN** 用户确认回退
- **THEN** 执行回退操作，更新状态

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


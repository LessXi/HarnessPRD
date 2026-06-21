# auto-advance Specification

## Purpose
TBD - created by archiving change ux-optimization-flow-closure. Update Purpose after archive.
## Requirements
### Requirement: 半自动推进机制
系统 SHALL 在每个阶段完成后显示提示栏，让用户选择是否继续生成下一个文档。

#### Scenario: 完成后显示提示
- **WHEN** 用户确认当前文档
- **THEN** 在内容区底部显示提示栏："是否继续生成下一个文档？"

#### Scenario: 提示栏按钮
- **WHEN** 用户查看提示栏
- **THEN** 显示"继续"、"跳过"、"返回"三个按钮

### Requirement: 自动推进开关
系统 SHALL 提供自动推进开关，控制是否自动进入下一阶段。

#### Scenario: 自动推进开启
- **WHEN** 自动推进开关开启，用户确认文档
- **THEN** 自动进入下一阶段，不显示提示栏

#### Scenario: 自动推进关闭
- **WHEN** 自动推进开关关闭，用户确认文档
- **THEN** 显示提示栏，等待用户选择

### Requirement: 取消生成功能
系统 SHALL 允许用户在生成过程中取消当前生成。

#### Scenario: 生成中显示取消按钮
- **WHEN** 文档正在生成中
- **THEN** 在提示栏显示"取消"按钮

#### Scenario: 取消生成
- **WHEN** 用户点击取消按钮
- **THEN** 停止生成，保留已生成的部分内容

#### Scenario: 取消后恢复
- **WHEN** 用户取消生成后
- **THEN** 显示"继续生成"按钮，可以从断点续写

### Requirement: 跳过阶段功能
系统 SHALL 允许用户跳过某些阶段，直接进入后续阶段。

#### Scenario: 跳过提示
- **WHEN** 用户选择跳过
- **THEN** 显示确认对话框："跳过X阶段，确定吗？"

#### Scenario: 跳过执行
- **WHEN** 用户确认跳过
- **THEN** 跳过该阶段，进入下一阶段


# view-state Specification

## Purpose
TBD - created by archiving change ux-optimization-flow-closure. Update Purpose after archive.
## Requirements
### Requirement: ViewState类型扩展
系统 SHALL 扩展ViewState类型，添加回退和待更新状态支持。

#### Scenario: 新增ViewState
- **WHEN** 系统定义ViewState类型
- **THEN** 包含所有现有状态，以及新的状态支持

### Requirement: 已完成步骤记录
系统 SHALL 在ProjectState中记录已完成步骤列表。

#### Scenario: 步骤完成记录
- **WHEN** 用户完成某个步骤
- **THEN** 将该步骤添加到completedSteps列表

#### Scenario: 步骤完成条件
- **WHEN** 用户确认文档或提交表单
- **THEN** 标记该步骤为已完成

### Requirement: 待更新状态支持
系统 SHALL 支持标记步骤为待更新状态。

#### Scenario: 待更新标记
- **WHEN** 用户回退到之前的步骤
- **THEN** 标记后续步骤为待更新

#### Scenario: 待更新清除
- **WHEN** 用户重新生成或确认文档
- **THEN** 清除该步骤的待更新状态

### Requirement: 状态转换验证
系统 SHALL 验证状态转换的合法性，确保流程安全有序。

#### Scenario: 合法转换验证
- **WHEN** 用户尝试状态转换
- **THEN** 验证转换是否在 `VALID_TRANSITIONS` 中定义，合法则执行

#### Scenario: 非法转换拒绝
- **WHEN** 用户尝试非法状态转换
- **THEN** 拒绝转换，显示错误提示

#### Scenario: generating_* 状态回退
- **WHEN** 用户在 `generating_*` 状态下点击「停止生成」
- **THEN** viewState 回退到对应的前一稳定状态（如 `generating_prd` → `ai_dialogue`）

### Requirement: 数据迁移兼容
系统 SHALL 兼容旧版本数据，自动忽略已移除的字段。

#### Scenario: 旧 autoAdvance 字段加载
- **WHEN** 系统加载含有 `autoAdvance` 字段的旧版本 ProjectState
- **THEN** 忽略该字段，不报错，使用手动推进模式

#### Scenario: 缺失字段默认值
- **WHEN** completedSteps 字段不存在
- **THEN** 初始化为空数组


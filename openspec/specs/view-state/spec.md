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

### Requirement: 自动推进设置
系统 SHALL 在ProjectState中保存自动推进设置。

#### Scenario: 设置保存
- **WHEN** 用户切换自动推进开关
- **THEN** 保存autoAdvance字段到ProjectState

#### Scenario: 设置读取
- **WHEN** 系统加载ProjectState
- **THEN** 读取autoAdvance字段，控制推进行为

### Requirement: 状态转换验证
系统 SHALL 验证状态转换的合法性，确保流程安全有序。

#### Scenario: 合法转换验证
- **WHEN** 用户尝试状态转换
- **THEN** 验证转换是否合法，合法则执行

#### Scenario: 非法转换拒绝
- **WHEN** 用户尝试非法状态转换
- **THEN** 拒绝转换，显示错误提示

### Requirement: 数据迁移兼容
系统 SHALL 兼容旧版本数据，自动迁移缺失字段。

#### Scenario: 旧数据加载
- **WHEN** 系统加载旧版本ProjectState
- **THEN** 自动添加缺失字段的默认值

#### Scenario: 新字段默认值
- **WHEN** completedSteps字段不存在
- **THEN** 初始化为空数组

#### Scenario: autoAdvance默认值
- **WHEN** autoAdvance字段不存在
- **THEN** 初始化为false（手动推进模式）


## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: 自动推进设置
**Reason**: autoAdvance 机制已移除，不再需要 `autoAdvance` 字段。
**Migration**: `ProjectState` 类型中移除 `autoAdvance: boolean` 字段。旧数据加载时忽略该字段。

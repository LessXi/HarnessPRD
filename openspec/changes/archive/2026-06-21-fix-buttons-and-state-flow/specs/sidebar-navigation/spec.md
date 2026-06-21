## MODIFIED Requirements

### Requirement: 操作按钮分组
系统 SHALL 将操作按钮分为导航组、主要操作组、次要操作组，分组显示在侧边栏中。

#### Scenario: 导航组按钮
- **WHEN** 用户查看导航组
- **THEN** 显示「返回上一步」和「下一步」按钮

#### Scenario: 审阅状态下无操作按钮
- **WHEN** 当前 viewState 为 `reviewing_prd` / `reviewing_api` / `reviewing_prompts`
- **THEN** 侧边栏不显示主要操作组和次要操作组按钮（确认、AI 优化、编辑等操作归 DocumentReview 独管）

#### Scenario: ai_dialogue 状态下操作按钮
- **WHEN** 当前 viewState 为 `ai_dialogue`
- **THEN** 侧边栏显示「生成 PRD」（主要操作）和「生成摘要」（次要操作）

#### Scenario: completed 状态下操作按钮
- **WHEN** 当前 viewState 为 `completed`
- **THEN** 侧边栏显示「开始新项目」（主要操作）

## REMOVED Requirements

### Requirement: 设置区域
**Reason**: autoAdvance 机制已移除，不再需要自动推进开关。
**Migration**: 移除 Sidebar 底部的设置区域 UI 及相关 `autoAdvance` 引用。

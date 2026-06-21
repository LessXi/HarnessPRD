# sidebar-navigation Specification

## Purpose
TBD - created by archiving change ux-optimization-flow-closure. Update Purpose after archive.
## Requirements
### Requirement: 侧边栏布局
系统 SHALL 采用侧边栏 + 内容区布局，侧边栏固定显示在左侧，内容区自适应剩余空间。

#### Scenario: 桌面端显示
- **WHEN** 用户在桌面端访问应用
- **THEN** 左侧显示固定宽度侧边栏（250px），右侧显示内容区

#### Scenario: 移动端显示
- **WHEN** 用户在移动端访问应用
- **THEN** 侧边栏以抽屉形式显示，点击按钮展开

### Requirement: 进度条显示
系统 SHALL 在侧边栏顶部显示进度条，展示所有阶段及当前进度。

#### Scenario: 进度条状态
- **WHEN** 用户查看进度条
- **THEN** 已完成步骤显示 ✓，当前步骤高亮，未完成步骤显示步骤编号

#### Scenario: 已完成步骤可点击
- **WHEN** 用户点击已完成步骤
- **THEN** 显示确认对话框，确认后回退到该步骤

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

### Requirement: 文档信息显示
系统 SHALL 在侧边栏显示当前文档的信息，包括字数、大小、复杂度。

#### Scenario: 文档信息更新
- **WHEN** 文档内容发生变化
- **THEN** 文档信息自动更新显示


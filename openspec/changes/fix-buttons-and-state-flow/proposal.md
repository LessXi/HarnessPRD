## Why

前端 `reviewing_*` 审阅状态下，Sidebar 操作区与 DocumentReview 工具栏渲染了重复的确认/AI优化/编辑按钮。同时存在三种行为不一致的回退入口（Sidebar「上一步」、步骤点击回退、CompletionPromptBar「返回」），autoAdvance 机制与手动推进逻辑交织导致状态不可预测。文档生成流式输出时内容区无高度约束，长文档撑出视口。

## What Changes

1. **消除按钮双重渲染**：移除 `reviewing_*` 状态下 Sidebar 的 primaryActions / secondaryActions，文档操作按钮归 DocumentReview 独管
2. **移除 autoAdvance**：删除 `autoAdvance` 字段及相关跳步逻辑，文档确认后始终显示 CompletionPromptBar 让用户手动选择下一步
3. **统一回退机制**：将 `handleNavigate`（上一步）、`handleRollback`（步骤点击）、`handleBack`（CompletionPromptBar）统一为一致的回退逻辑，回退时清除受影响步骤的 `confirmed` 标志并设置 `pendingUpdates`
4. **新增「停止生成」按钮**：`generating_*` 状态下提供中断按钮，前端 abort SSE 连接后回退到生成前状态
5. **修复显示框过长**：DocumentReview 内容区添加 `max-h-[calc(100vh-<offset>)] overflow-y-auto`，长文档内部滚动
6. **规整状态机**：输出 ViewState → 操作按钮 → 回退目标 的统一映射表，消除分散的条件分支

## Capabilities

### New Capabilities
- `stop-generation`: 文档生成过程中提供前端中断能力，abort SSE 连接并回退到生成前状态

### Modified Capabilities
- `auto-advance`: **移除**该 capability，autoAdvance 字段及关联跳步逻辑全部删除
- `sidebar-navigation`: 移除 `reviewing_*` 状态下的操作按钮渲染，侧边栏回归纯进度导航；移除 `autoAdvance` 相关分支
- `step-rollback`: 统一三种回退入口为单一 `handleGoBack`，定义各状态的回退目标表和受影响步骤清理规则
- `view-state`: 移除 `autoAdvance` 字段引用，确保 ViewState 转换逻辑与回退规则一致

## Impact

- **前端文件**：`App.tsx`、`Sidebar.tsx`、`DocumentReview.tsx`、`CompletionPromptBar.tsx`、`types/index.ts`
- **数据迁移**：localStorage 加载时忽略旧 `autoAdvance` 字段（兼容迁移，不报错）
- **无后端影响**：不修改 API、Skill Engine 或 SSE 端点

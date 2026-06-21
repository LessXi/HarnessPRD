# Comet Design Handoff

- Change: fix-buttons-and-state-flow
- Phase: design
- Mode: compact
- Context hash: fe31e14fac47b7785ecb5eef6129fd37d5dbdb873e36237013363bef17a5117b

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/fix-buttons-and-state-flow/proposal.md

- Source: openspec/changes/fix-buttons-and-state-flow/proposal.md
- Lines: 1-29
- SHA256: 388c89ae7410d6ae626176221317a1040c6f8e900f11761e3fc04b18c46f4bd5

```md
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
```

## openspec/changes/fix-buttons-and-state-flow/design.md

- Source: openspec/changes/fix-buttons-and-state-flow/design.md
- Lines: 1-94
- SHA256: 1ed8203d3fa5bb609f5c286e0687b060f5b9f9275b6d8dbdfd03b51fe29483eb

[TRUNCATED]

```md
## Context

HarnessPRD 前端在审阅状态下存在按钮双重渲染问题：Sidebar 通过 `primaryActions`/`secondaryActions` 传递操作按钮，同时 DocumentReview 组件内部也渲染了相同功能的工具栏按钮。此外，存在三种行为不一致的回退入口，`autoAdvance` 机制与手动推进逻辑交织，文档生成时内容区无高度约束。

## Goals / Non-Goals

**Goals:**
- 消除 `reviewing_*` 状态下 Sidebar 与 DocumentReview 的按钮重复
- 统一回退入口为单一 `handleGoBack`，含确认对话框和受影响步骤清理
- 移除 `autoAdvance` 机制，始终手动推进
- 新增 `generating_*` 状态下的「停止生成」按钮
- 修复 DocumentReview 内容区显示框过长问题
- 输出 ViewState → 按钮 → 回退目标的完整映射表

**Non-Goals:**
- 不修改后端 API / Skill Engine / SSE 端点
- 不变更 localStorage 数据结构（兼容迁移旧 `autoAdvance`）
- 不改变 `form_editing` / `ai_dialogue` / `completed` 状态下的按钮布局
- 「停止生成」纯前端 abort，不依赖后端中断端点

## Decisions

### 1. 按钮架构：操作按钮归 DocumentReview 独管

**选择**：移除 `reviewing_*` 状态下 Sidebar 的 `primaryActions` / `secondaryActions` 推送。文档操作（确认、AI 优化、编辑）全部由 DocumentReview 内部工具栏管理。

**替代方案**：
- 方案 B（DocumentReview 移除按钮，归 Sidebar 管）：破坏组件封装性，DocumentReview 内部编辑模式(textarea 切换)需要重新设计
- 方案 C（两者保留但去重）：逻辑分散，易再次不一致

**实现**：修改 `App.tsx` 中 `primaryActions` / `secondaryActions` 的构建逻辑（约 948-990 行），`reviewing_*` 状态下返回空数组。Sidebar 仅保留进度导航和「上一步/下一步」按钮。

### 2. 回退统一：单一 `handleGoBack(targetState)`

**选择**：合并当前三种回退入口（`handleNavigate`、`handleRollback`、`handleBack`）为统一的 `handleGoBack(targetState)`：
1. 基于目标状态计算受影响步骤（targetState 之后的所有已确认步骤）
2. 显示确认对话框，列出受影响步骤
3. 用户确认后：清除受影响步骤的 `confirmed` 标志 → 添加 `pendingUpdates` → 更新 `viewState` → 必要时调整 `completedSteps`
4. 「停止生成」复用同一逻辑：targetState = 生成前的稳定状态

**替代方案**：保留三种入口各自逻辑 → 持续不一致，维护负担重。

### 3. 移除 autoAdvance

**选择**：从 `ProjectState` 类型中移除 `autoAdvance` 字段，删除 `App.tsx` 中所有 `autoAdvance` 相关的条件分支。文档确认后始终显示 `CompletionPromptBar`。

**数据迁移**：`types/index.ts` 的 `loadProject()` / `createDefaultProject()` 中忽略旧 `autoAdvance` 字段，不报错。

### 4. 显示框修复：固定高度容器

**选择**：DocumentReview 内容区 `<div className="flex-1 overflow-y-auto">` 替换为：
```
<div className="flex-1 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 12rem)' }}>
```

12rem 覆盖：顶部导航 (~4rem) + DocumentReview header (~3rem) + 底部工具栏 (~3rem) + 安全边距 (~2rem)。

### 5. 状态机规范

**状态 → 按钮映射表**：

| ViewState | Sidebar 操作 | DocumentReview 操作 | 可回退至 |
|-----------|-------------|-------------------|---------|
| `form_editing` | — | —（表单页无 DocumentReview） | — |
| `ai_dialogue` | 生成 PRD / 生成摘要 | —（聊天页无 DocumentReview） | `form_editing` |
| `generating_prd` | — | 停止生成 | `ai_dialogue` |
| `reviewing_prd` | 上一步/下一步 | 确认 + AI 优化 + 编辑 | `ai_dialogue`, `form_editing` |
| `generating_api` | — | 停止生成 | `reviewing_prd`, `ai_dialogue` |
| `reviewing_api` | 上一步/下一步 | 确认 + AI 优化 + 编辑 | `reviewing_prd`, `ai_dialogue` |
| `generating_prompts` | — | 停止生成 | `reviewing_api`, `reviewing_prd`, `ai_dialogue` |
| `reviewing_prompts` | 上一步/下一步 | 确认 + AI 优化 + 编辑 | `reviewing_api`, `reviewing_prd`, `ai_dialogue` |
| `completed` | 开始新项目 | —（CompletionSummary 自带预览/下载/复制） | — |

**回退清理规则**：回退至目标状态时，目标状态之后的所有文档 `confirmed` 重置为 `false`，对应步骤加入 `pendingUpdates`。`completedSteps` 移除以目标状态为界的后续步骤。

### 6. Debug 埋点接入

**选择**：在核心状态转换函数中注入 debug 探针（`debug-instrument`），便于实施期间追踪状态机行为。

**埋点位置**：
```

Full source: openspec/changes/fix-buttons-and-state-flow/design.md

## openspec/changes/fix-buttons-and-state-flow/tasks.md

- Source: openspec/changes/fix-buttons-and-state-flow/tasks.md
- Lines: 1-59
- SHA256: 985d0bf7c19f370bde9768c3c71677abba6d5ac39c10db23fe61c34d793c9a93

```md
## 1. 类型定义与数据迁移 (types/index.ts)

- [ ] 1.1 从 `ProjectState` 接口中移除 `autoAdvance: boolean` 字段 [P0]
- [ ] 1.2 更新 `createDefaultProject()` 不再初始化 `autoAdvance` [P0]
- [ ] 1.3 更新 `loadProject()` 数据迁移逻辑：忽略旧 `autoAdvance` 字段，不报错 [P0]
- [ ] 1.4 更新 `VALID_TRANSITIONS`：添加 `generating_prd` → `ai_dialogue`、`generating_api` → `reviewing_prd`、`generating_prompts` → `reviewing_api` 回退边 [P0]
- [ ] 1.5 更新 `isValidStateTransition`：`generating_*` 状态允许回退到对应前一稳定状态 [P0]

## 2. Sidebar 按钮清理 (Sidebar.tsx)

- [ ] 2.1 移除 `reviewing_*` 状态下 Sidebar 的 `primaryActions` / `secondaryActions` 渲染（确认/AI优化/编辑按钮不再出现在侧边栏）[P0]
- [ ] 2.2 移除 Sidebar 底部设置区域的 `autoAdvance` 开关 UI [P0]
- [ ] 2.3 确保 Sidebar「上一步」按钮调用统一的 `handleGoBack` 而非旧的 `handleNavigate` [P0]

## 3. 统一回退机制 (App.tsx)

- [ ] 3.1 实现 `handleGoBack(targetState: ViewState)` 函数 [P0]
- [ ] 3.2 handleGoBack 内部逻辑：计算受影响步骤 → 显示确认对话框 → 确认后重置 `confirmed` → 添加 `pendingUpdates` → 更新 `viewState` → 调整 `completedSteps` [P0]
- [ ] 3.3 替换 `handleNavigate` 中的后向导航逻辑为调用 `handleGoBack` [P0]
- [ ] 3.4 替换 `handleRollback` 为调用 `handleGoBack` [P0]
- [ ] 3.5 更新 `handleBack`（CompletionPromptBar「返回」）：调用 `handleGoBack` 回退到上一个稳定状态，而非仅关闭提示栏 [P1]
- [ ] 3.6 移除 `App.tsx` 中所有 `autoAdvance` 相关的条件分支 [P0]
- [ ] 3.7 更新 `handleConfirmDoc`：移除 autoAdvance 检查，始终设置 `showCompletionPrompt = true` [P0]

## 4. 停止生成功能 (App.tsx + DocumentReview.tsx)

- [ ] 4.1 在 `generateDocumentStream` 调用处添加 `AbortController`，保存引用 [P0]
- [ ] 4.2 实现 `handleStopGeneration()`：调用 `AbortController.abort()` → 调用 `handleGoBack` 回退到生成前状态 [P0]
- [ ] 4.3 在 DocumentReview 工具栏添加「停止生成」按钮，仅在 `isStreaming && !isReviewing` 时显示 [P0]
- [ ] 4.4 `generating_*` 状态下向 DocumentReview 传递 `onStop` prop [P0]

## 5. 显示框修复 (DocumentReview.tsx)

- [ ] 5.1 文档内容区容器添加 `style={{ maxHeight: 'calc(100vh - 12rem)' }}` [P0]
- [ ] 5.2 确认 `overflow-y-auto` 在固定高度下正确触发内部滚动 [P0]

## 6. 按钮一致性收尾 (App.tsx + 全局)

- [ ] 6.1 删除 `handleDocEdit`（旧 Sidebar 编辑按钮的保存模式处理器），仅保留 DocumentReview 内部 textarea 编辑模式 [P1]
- [ ] 6.2 清理 `primaryActions` / `secondaryActions` 构建逻辑中不再需要的分支 [P1]
- [ ] 6.3 确保 `generating_*` 状态下 Sidebar 不渲染任何操作按钮 [P0]

## 7. Debug 埋点接入 (App.tsx)

- [ ] 7.1 在 `handleGoBack` 注入 trace 探针：记录 `targetState`、受影响步骤、`completedSteps` 变更 [P1]
- [ ] 7.2 在 `handleConfirmDoc` 注入 log 探针：记录 `docType`、viewState 变更、`showCompletionPrompt` 设置 [P1]
- [ ] 7.3 在 `switchView` 注入 trace 探针：记录每次 ViewState 转换的 from → to [P1]
- [ ] 7.4 在 `handleStopGeneration` 注入 log 探针：记录 abort 调用、回退目标状态 [P1]
- [ ] 7.5 在 `generateDocumentStream` 调用处注入 timer 探针：记录文档生成耗时 [P1]
- [ ] 7.6 回归验证通过后运行 `debug-cleanup` 移除所有探针 [P0]

## 8. 回归验证

- [ ] 8.1 `form_editing` → `ai_dialogue` → `generating_prd` → `reviewing_prd` → ... → `completed` 全程遍历，验证每步按钮状态 [P0]
- [ ] 8.2 验证回退：从 `reviewing_prompts` 回退到 `ai_dialogue`，确认对话框正确，affected steps confirmed 重置 [P0]
- [ ] 8.3 验证停止生成：`generating_prd` 状态点击停止 → SSE 中断 → 回到 `ai_dialogue` [P0]
- [ ] 8.4 验证显示框：生成长文档时内容区不撑出视口，内部滚动正常 [P0]
- [ ] 8.5 验证旧数据兼容：加载含 `autoAdvance` 字段的 localStorage 数据不报错 [P1]
- [ ] 8.6 验证无按钮重复：`reviewing_*` 状态 Sidebar 仅有进度导航，DocumentReview 工具栏完整 [P0]
```

## openspec/changes/fix-buttons-and-state-flow/specs/auto-advance/spec.md

- Source: openspec/changes/fix-buttons-and-state-flow/specs/auto-advance/spec.md
- Lines: 1-17
- SHA256: 26ea0dcc7593f515930d63f2ce9aa0760eedebb052207bff9fe7dbdb0eed0b83

```md
## REMOVED Requirements

### Requirement: 半自动推进机制
**Reason**: 移除 autoAdvance 机制，改为始终手动推进。文档确认后始终显示 CompletionPromptBar 让用户明确选择下一步，消除自动/手动双模式带来的状态不可预测性。
**Migration**: `autoAdvance` 字段从 `ProjectState` 中移除。旧 localStorage 数据加载时忽略该字段。`CompletionPromptBar` 在每次文档确认后显示（之前仅在 `autoAdvance=false` 时显示）。

### Requirement: 自动推进开关
**Reason**: 同上，不再需要自动/手动模式切换。
**Migration**: Sidebar 设置区域移除自动推进开关 UI。

### Requirement: 取消生成功能
**Reason**: 被新的 `stop-generation` capability 替代，提供更明确的「停止生成」按钮和行为定义。
**Migration**: 使用 `generating_*` 状态下 DocumentReview 工具栏中的「停止生成」按钮。

### Requirement: 跳过阶段功能
**Reason**: 移除。CompletionPromptBar 的「跳过」按钮保留，但不再作为独立 capability。跳过逻辑简化为直接进入下一阶段，无需确认对话框。
**Migration**: CompletionPromptBar 中「跳过」按钮直接触发下一阶段推进，不显示二次确认。
```

## openspec/changes/fix-buttons-and-state-flow/specs/sidebar-navigation/spec.md

- Source: openspec/changes/fix-buttons-and-state-flow/specs/sidebar-navigation/spec.md
- Lines: 1-26
- SHA256: 25cf3d817c4a25352972db21e23a4b52ab5fedf29a3613e725c4daf19ea562c0

```md
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
```

## openspec/changes/fix-buttons-and-state-flow/specs/step-rollback/spec.md

- Source: openspec/changes/fix-buttons-and-state-flow/specs/step-rollback/spec.md
- Lines: 1-42
- SHA256: 61245aa17cc155fae538dc70118555bbb8ccefdc362d31150d4f80cdf3135aea

```md
## MODIFIED Requirements

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

### Requirement: CompletionPromptBar 返回行为
系统 SHALL 使 CompletionPromptBar 的「返回」按钮也触发统一回退逻辑。

#### Scenario: 提示栏返回
- **WHEN** 用户点击 CompletionPromptBar 的「返回」按钮
- **THEN** 触发 `handleGoBack`，回退到上一个稳定状态（而非仅关闭提示栏）
```

## openspec/changes/fix-buttons-and-state-flow/specs/stop-generation/spec.md

- Source: openspec/changes/fix-buttons-and-state-flow/specs/stop-generation/spec.md
- Lines: 1-20
- SHA256: c97a27a3f929add09c50e894f4ab9aed45dd809742716b434abedf29b95fb530

```md
## ADDED Requirements

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
```

## openspec/changes/fix-buttons-and-state-flow/specs/view-state/spec.md

- Source: openspec/changes/fix-buttons-and-state-flow/specs/view-state/spec.md
- Lines: 1-33
- SHA256: c727092cd3599b6bd9d50f8fac414d8d1eff886e2a534ef2eb3077844474e0b7

```md
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
```


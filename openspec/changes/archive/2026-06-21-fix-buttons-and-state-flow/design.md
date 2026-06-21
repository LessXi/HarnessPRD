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
- `handleGoBack(targetState)` — trace 探针记录回退目标、受影响步骤
- `handleConfirmDoc(docType)` — log 探针记录确认的文档类型、viewState 变更
- `switchView(newState)` — trace 探针记录每次 ViewState 转换
- `handleStopGeneration()` — log 探针记录 SSE abort 和回退目标
- `generateDocumentStream()` — timer 探针记录生成耗时

**清理**：实施完毕、回归验证通过后，用 `debug-cleanup` 移除所有探针，不留生产代码痕迹。

## Risks / Trade-offs

- **[风险] 旧 localStorage 含 autoAdvance 字段** → 兼容迁移：加载时忽略未知字段，不报错
- **[风险] 「停止生成」后 SSE 后端可能继续处理** → 接受：后端下次写入时发现连接断开自然停止；不影响数据一致性（下次重新生成覆盖）
- **[风险] 回退时 confirmed 重置后用户需重新确认** → 符合预期：回退意味着之前确认作废
- **[权衡] 移除 autoAdvance 增加一次点击** → 换来确定性：用户始终明确知道下一步行为

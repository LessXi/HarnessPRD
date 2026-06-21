## 1. 类型定义与数据迁移 (types/index.ts)

- [x] 1.1 从 `ProjectState` 接口中移除 `autoAdvance: boolean` 字段 [P0]
- [x] 1.2 更新 `createDefaultProject()` 不再初始化 `autoAdvance` [P0]
- [x] 1.3 更新 `loadProject()` 数据迁移逻辑：忽略旧 `autoAdvance` 字段，不报错 [P0]
- [x] 1.4 更新 `VALID_TRANSITIONS`：添加 `generating_prd` → `ai_dialogue`、`generating_api` → `reviewing_prd`、`generating_prompts` → `reviewing_api` 回退边 [P0]
- [x] 1.5 更新 `isValidStateTransition`：`generating_*` 状态允许回退到对应前一稳定状态 [P0]

## 2. Sidebar 按钮清理 (Sidebar.tsx)

- [x] 2.1 移除 `reviewing_*` 状态下 Sidebar 的 `primaryActions` / `secondaryActions` 渲染（确认/AI优化/编辑按钮不再出现在侧边栏）[P0]
- [x] 2.2 移除 Sidebar 底部设置区域的 `autoAdvance` 开关 UI [P0]
- [x] 2.3 确保 Sidebar「上一步」按钮调用统一的 `handleGoBack` 而非旧的 `handleNavigate` [P0]

## 3. 统一回退机制 (App.tsx)

- [x] 3.1 实现 `handleGoBack(targetState: ViewState)` 函数 [P0]
- [x] 3.2 handleGoBack 内部逻辑：计算受影响步骤 → 显示确认对话框 → 确认后重置 `confirmed` → 添加 `pendingUpdates` → 更新 `viewState` → 调整 `completedSteps` [P0]
- [x] 3.3 替换 `handleNavigate` 中的后向导航逻辑为调用 `handleGoBack` [P0]
- [x] 3.4 替换 `handleRollback` 为调用 `handleGoBack` [P0]
- [x] 3.5 更新 `handleBack`（CompletionPromptBar「返回」）：调用 `handleGoBack` 回退到上一个稳定状态，而非仅关闭提示栏 [P1]
- [x] 3.6 移除 `App.tsx` 中所有 `autoAdvance` 相关的条件分支 [P0]
- [x] 3.7 更新 `handleConfirmDoc`：移除 autoAdvance 检查，始终设置 `showCompletionPrompt = true` [P0]

## 4. 停止生成功能 (App.tsx + DocumentReview.tsx)

- [ ] 4.1 在 `generateDocumentStream` 调用处添加 `AbortController`，保存引用 [P0]
- [ ] 4.2 实现 `handleStopGeneration()`：调用 `AbortController.abort()` → 调用 `handleGoBack` 回退到生成前状态 [P0]
- [ ] 4.3 在 DocumentReview 工具栏添加「停止生成」按钮，仅在 `isStreaming && !isReviewing` 时显示 [P0]
- [ ] 4.4 `generating_*` 状态下向 DocumentReview 传递 `onStop` prop [P0]

## 5. 显示框修复 (DocumentReview.tsx)

- [x] 5.1 文档内容区容器添加 `style={{ maxHeight: 'calc(100vh - 12rem)' }}` [P0]
- [x] 5.2 确认 `overflow-y-auto` 在固定高度下正确触发内部滚动 [P0]

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

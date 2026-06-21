---
change: fix-buttons-and-state-flow
design-doc: docs/superpowers/specs/2026-06-21-fix-buttons-and-state-flow-design.md
base-ref: 6a23cdecdac27cccc35b0060f84323204d5ba376
---

# 实施计划：按钮去重 & 状态机修复

## 概览

修复 HarnessPRD 前端三类问题：按钮双重渲染（Sidebar 与 DocumentReview 各自渲染确认/AI优化/编辑按钮）、状态不一致（三种回退入口行为不同，autoAdvance 机制与手动推进交织）、显示框溢出（流式输出无高度约束）。改动涉及 5 个文件（`App.tsx`、`Sidebar.tsx`、`DocumentReview.tsx`、`types/index.ts`、`CompletionPromptBar.tsx`），7 组任务共 36 个子任务。

## 依赖关系图

```
任务 1 (类型/数据迁移) ── 基础依赖 ──→ 任务 2 (Sidebar 清理) ──→ 任务 6 (收尾)
                                     │
任务 3 (统一回退) ── 核心机制 ────────┼──→ 任务 4 (停止生成)
                                     │
任务 5 (显示框修复) ── 独立 ──────────┘
                                                      ↘
                                              任务 7 (Debug 埋点) ── 贯穿全流程
                                                      ↓
                                              任务 8 (回归验证) ── 收束
```

**执行顺序建议**：
1. 先做任务 5（独立、无依赖，可并行）
2. 再做任务 1（基础类型变更）
3. 任务 3（核心机制，依赖于任务 1）
4. 任务 2 + 任务 4（依赖于任务 3，可并行）
5. 任务 6（收尾，依赖于任务 2、3）
6. 任务 7（Debug 埋点，可与上述任务并行注入，最后移除）
7. 任务 8（最终验证）

---

### 任务 1：类型定义与数据迁移 (P0)

**目标**：从 `ProjectState` 接口移除 `autoAdvance`，更新状态转换表，添加数据迁移兼容逻辑。

**涉及文件**：
- `frontend/src/types/index.ts`

**子任务与关键实现要点**：

1.1 **移除 `autoAdvance` 字段** — 从 `ProjectState` 接口中删除 `autoAdvance: boolean` [P0]

1.2 **更新 `createDefaultProject()`** — 不再初始化 `autoAdvance` [P0]

1.3 **更新 `loadProject()` 数据迁移** — 读取旧 localStorage 数据时，解构忽略 `autoAdvance` 字段，合并 `createDefaultProject()` 确保缺失字段有默认值 [P0]
```typescript
const { autoAdvance, ...cleanData } = rawData;
return { ...createDefaultProject(), ...cleanData };
```

1.4 **更新 `VALID_TRANSITIONS`** — 添加三条回退边：`generating_prd` → `ai_dialogue`、`generating_api` → `reviewing_prd`、`generating_prompts` → `reviewing_api` [P0]

1.5 **更新 `isValidStateTransition`** — `generating_*` 状态允许回退到对应前一稳定状态 [P0]

**验收标准**：
- `ProjectState` 接口无 `autoAdvance`
- 含旧 `autoAdvance` 字段的 localStorage 数据加载不报错
- `VALID_TRANSITIONS` 包含三条生成→稳定状态回退边
- `isValidStateTransition` 正确放行回退状态转换

**依赖**：无

**工作量**：S（20 分钟）

---

### 任务 2：Sidebar 按钮清理 (P0)

**目标**：文档操作按钮归 DocumentReview 独管，Sidebar 仅保留进度导航和操作组的「上一步/下一步」「生成」「开始新项目」按钮。

**涉及文件**：
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/App.tsx`（`primaryActions`/`secondaryActions` 构建）

**子任务与关键实现要点**：

2.1 **移除 reviewing_* 状态的 primaryActions/secondaryActions** — `App.tsx` 中构建 `primaryActions`/`secondaryActions` 的逻辑（~948-990 行）：`reviewing_*` 状态下返回空数组，不渲染确认/AI优化/编辑按钮 [P0]

2.2 **移除 autoAdvance 开关 UI** — `Sidebar.tsx` 底部设置区域删除 autoAdvance toggle [P0]

2.3 **Sidebar「上一步」调用 `handleGoBack`** — 确保 Sidebar 的「上一步」按钮调用统一的 `handleGoBack(targetState)` 而非旧的 `handleNavigate` [P0]

**验收标准**：
- `reviewing_*` 状态下 Sidebar 仅有进度导航（上一步/下一步），无操作按钮
- Sidebar 底部无 autoAdvance 开关
- 「上一步」回调指向 `handleGoBack`

**依赖**：任务 1、任务 3（需要 `handleGoBack` 存在）

**工作量**：S（30 分钟）

---

### 任务 3：统一回退机制 (P0)

**目标**：实现 `handleGoBack(targetState: ViewState)` 作为统一的后向导航入口，替换三处分散的回退逻辑（`handleNavigate` 后向、`handleRollback`、`handleBack`）。

**涉及文件**：
- `frontend/src/App.tsx`

**子任务与关键实现要点**：

3.1 **实现 `handleGoBack(targetState: ViewState)`** [P0]
```typescript
const handleGoBack = useCallback((targetState: ViewState) => {
  const currentIdx = STEP_INDEX_MAP[viewState];
  const targetIdx = STEP_INDEX_MAP[targetState];
  if (targetIdx >= currentIdx) return;

  const affectedSteps = STEPS.filter((_, i) => i > targetIdx);
  const affectedDocs = affectedSteps
    .map(s => DOC_TYPE_BY_STEP[s])
    .filter(Boolean)
    .filter(docType => project[docType].confirmed);

  if (affectedDocs.length === 0) {
    switchView(targetState);
    return;
  }

  showConfirmDialog({...});
}, [viewState, project, switchView]);
```

3.2 **确认对话框逻辑** — 计算受影响步骤 → 找出已 confirmed 的文档 → 显示确认对话框 → 确认后：重置 `confirmed` → 添加 `pendingUpdates` → 更新 `viewState` → 裁剪 `completedSteps` → 关闭 `showCompletionPrompt` [P0]

3.3 **替换 `handleNavigate` 后向导航** — `handleNavigate` 中的后向导航（`targetIdx < currentIdx` 分支）改为调用 `handleGoBack` [P0]

3.4 **替换 `handleRollback`** — 删除或重写为调用 `handleGoBack` [P0]

3.5 **更新 `handleBack`（CompletionPromptBar「返回」）** — 调用 `handleGoBack` 回退到上一个稳定状态，而非仅关闭提示栏 [P1]

3.6 **移除 autoAdvance 条件分支** — 删除 `App.tsx` 中所有 `autoAdvance` 相关的条件判断（如自动推进逻辑）[P0]

3.7 **更新 `handleConfirmDoc`** — 移除 autoAdvance 检查，始终设置 `showCompletionPrompt = true` [P0]

**验收标准**：
- 从 `reviewing_prompts` 调用 `handleGoBack("ai_dialogue")` → 确认对话框 → 重置 PRD/API/Prompts 的 confirmed → 更新 completedSteps → 跳转到 ai_dialogue
- 回退到 `form_editing`（开始新项目）重置全部文档
- 前后向导航不出错（后向禁用，前向放行）
- `handleNavigate`、`handleRollback`、`handleBack` 三个入口行为一致

**依赖**：任务 1（类型和 `VALID_TRANSITIONS` 更新）

**工作量**：M（1.5 小时）

---

### 任务 4：停止生成功能 (P0)

**目标**：实现 SSE 流式请求的中止机制，`generating_*` 状态下显示停止生成按钮，点击后中断请求并回退到生成前状态。

**涉及文件**：
- `frontend/src/App.tsx`
- `frontend/src/components/DocumentReview.tsx`

**子任务与关键实现要点**：

4.1 **AbortController 集成** — 在 `generateDocumentStream` 调用前创建新 `AbortController`，保存引用到 `abortControllerRef`；传给 `fetch(url, { signal })`；`readStream` 的 `onDone` 回调中清除引用 [P0]

4.2 **实现 `handleStopGeneration()`** — 调用 `abortControllerRef.current?.abort()` → 根据当前 `viewState` 确定回退目标（`generating_prd → ai_dialogue`、`generating_api → reviewing_prd`、`generating_prompts → reviewing_api`）→ 调用 `handleGoBack(preGenState)` [P0]

4.3 **DocumentReview「停止生成」按钮** — 工具栏添加停止生成按钮，仅在 `isStreaming && !isReviewing`（即 `generating_*` 状态）时显示 [P0]

4.4 **传递 `onStop` prop** — `generating_*` 状态下向 DocumentReview 传递 `handleStopGeneration` 作为 `onStop` prop [P0]

**验收标准**：
- `generating_prd` 状态点击停止 → SSE 请求中断 → 回到 `ai_dialogue`
- 停止后 `abortControllerRef.current` 为 null
- 停止生成按钮在 `reviewing_*` 状态下不显示

**依赖**：任务 3（需要 `handleGoBack`）

**工作量**：S（40 分钟）

---

### 任务 5：显示框修复 (P0)

**目标**：文档内容区添加固定高度约束，长文档流式输出不撑出视口，内部滚动正常。

**涉及文件**：
- `frontend/src/components/DocumentReview.tsx`

**子任务与关键实现要点**：

5.1 **内容区 max-height** — 文档内容区容器添加 `style={{ maxHeight: 'calc(100vh - 12rem)' }}`，其中 12rem = 顶部导航(~4rem) + DocumentReview header(~3rem) + 底部工具栏(~3rem) + 安全边距(~2rem) [P0]

5.2 **确认滚动生效** — 已有 `flex-1 overflow-y-auto` class，验证 `maxHeight` 约束下内部滚动正常触发 [P0]

**验收标准**：
- 生成长文档（5000+ 字）时内容区固定高度，不撑出视口
- 内容区内部可滚动
- 页面整体无额外滚动条（仅内容区内部滚动）

**依赖**：无（可独立执行，推荐首批完成）

**工作量**：XS（10 分钟）

---

### 任务 6：按钮一致性收尾 (P1)

**目标**：清理不再需要的按钮相关代码，确保 `generating_*` 状态 Sidebar 不渲染操作按钮。

**涉及文件**：
- `frontend/src/App.tsx`

**子任务与关键实现要点**：

6.1 **删除 `handleDocEdit`** — 旧 Sidebar 编辑按钮的保存模式处理器，DocumentReview 内部已有 textarea 编辑模式替代 [P1]

6.2 **清理 primaryActions/secondaryActions 分支** — 构建逻辑中不再需要的条件分支（如 `reviewing_*` 分支已变为空数组）[P1]

6.3 **`generating_*` 状态按钮控制** — 确保 Sidebar 在 `generating_*` 状态下不渲染任何操作按钮（仅进度导航可见）[P0]

**验收标准**：
- `App.tsx` 无 `handleDocEdit` 函数
- `sideActions` 构建逻辑简洁，无死分支
- `generating_*` 状态 Sidebar 仅进度导航

**依赖**：任务 2、任务 3

**工作量**：S（20 分钟）

---

### 任务 7：Debug 埋点接入 (P1)

**目标**：在关键函数注入 debug 探针，便于回归验证时追踪状态转换和逻辑执行。回归验证通过后全部移除。

**涉及文件**：
- `frontend/src/App.tsx`

**子任务与关键实现要点**：

7.1 **`handleGoBack` trace 探针** — 记录 `targetState`、受影响步骤、`completedSteps` 变更 [P1]

7.2 **`handleConfirmDoc` log 探针** — 记录 `docType`、viewState 变更、`showCompletionPrompt` 设置 [P1]

7.3 **`switchView` trace 探针** — 记录每次 ViewState 转换的 from → to [P1]

7.4 **`handleStopGeneration` log 探针** — 记录 abort 调用、回退目标状态 [P1]

7.5 **`generateDocumentStream` timer 探针** — 记录文档生成耗时 [P1]

7.6 **回归验证通过后清理** — 运行 `debug-cleanup` 移除所有探针 [P0]

**验收标准**：
- 探针注入后不改变函数行为
- `debug-cleanup` 执行后源码无残留探针
- 所有探针在合并前被移除（仅用于验证阶段）

**依赖**：任务 3、任务 4（注入目标函数存在后即可执行，可与实现任务并行）

**工作量**：S（20 分钟）

---

### 任务 8：回归验证 (P0)

**目标**：全程遍历状态流转，验证按钮去重、回退机制、停止生成、显示框修复和旧数据兼容。

**涉及文件**：
- 无新增代码，纯手动/E2E 验证

**子任务与验收场景**：

8.1 **全程状态遍历** — `form_editing` → `ai_dialogue` → `generating_prd` → `reviewing_prd` → `generating_api` → `reviewing_api` → `generating_prompts` → `reviewing_prompts` → `completed`，每步验证按钮状态正确 [P0]
- `reviewing_*`：Sidebar 仅「上一步/下一步」，DocumentReview 含「确认」「AI优化」「编辑」
- `generating_*`：DocumentReview 含「停止生成」，Sidebar 无操作按钮
- `completed`：Sidebar 含「开始新项目」

8.2 **回退验证** — 从 `reviewing_prompts` 回退到 `ai_dialogue`：确认对话框正确显示受影响文档（PRD、API、Prompts）→ 确认后 confirmed 全部重置 → pendingUpdates 标记 → completedSteps 裁剪 → viewState 更新 [P0]

8.3 **停止生成验证** — `generating_prd` 状态点击「停止生成」→ SSE 请求中断 → 状态回到 `ai_dialogue` → 无残留流数据 [P0]

8.4 **显示框验证** — 生成长文档时内容区 `maxHeight` 固定，内部滚动正常，页面整体无溢出 [P0]

8.5 **旧数据兼容** — 用含 `autoAdvance` 字段的 localStorage 旧数据初始化，无 JS 错误 [P1]

8.6 **按钮去重验证** — `reviewing_*` 状态下 Sidebar 无「确认」「AI优化」「编辑」按钮，DocumentReview 工具栏完整 [P0]

**依赖**：任务 1~6 全部完成（任务 7 可选）

**工作量**：M（1 小时）

---

## 工作量汇总

| 任务 | 优先级 | 预估 | 依赖 | 文件数 |
|------|--------|------|------|--------|
| 1. 类型/数据迁移 | P0 | 20m | - | 1 |
| 2. Sidebar 清理 | P0 | 30m | 1, 3 | 2 |
| 3. 统一回退机制 | P0 | 1.5h | 1 | 1 |
| 4. 停止生成功能 | P0 | 40m | 3 | 2 |
| 5. 显示框修复 | P0 | 10m | - | 1 |
| 6. 按钮收尾 | P1 | 20m | 2, 3 | 1 |
| 7. Debug 埋点 | P1 | 20m | 3, 4 | 1 |
| 8. 回归验证 | P0 | 1h | 1~6 | 0 |
| **合计** | | **~4.5h** | | **5 文件** |

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| `handleGoBack` 中 affectedSteps 计算错误导致错误重置文档 | 高 | 对照回退映射表逐条写单元测试，确保每对回退路径的 affectedDocs 正确 |
| 三处回退入口替换后遗留旧逻辑 | 高 | 替换后 grep `handleNavigate\|handleRollback\|autoAdvance` 确认无残留 |
| AbortController 与 readStream 竞态（abort 后 onDone 仍触发） | 中 | `handleStopGeneration` 中设置标志位跳过 abort 后的 onDone 回调 |
| 旧数据兼容：旧 localStorage 存在额外未知字段 | 低 | `createDefaultProject()` 合并模式自动丢弃未知字段，不抛异常 |
| CSS calc(100vh) 在不同浏览器表现差异 | 低 | 用 `h-screen` + `flex` 布局兜底，calc 作为主要约束 |

## 分支策略

- 在已有分支 `feat/fix-buttons-state-flow` 上开发（如不存在则基于 `main` 创建）
- 合并前必须通过任务 8（回归验证）全部验证项
- 建议按依赖顺序逐个提交：任务 5 → 任务 1 → 任务 3 → 任务 2 → 任务 4 → 任务 6 → 任务 7 → debug-cleanup → 任务 8
- 合并前从 `main` rebase，确保无冲突

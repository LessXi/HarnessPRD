---
comet_change: fix-buttons-and-state-flow
role: technical-design
canonical_spec: openspec
---

# 按钮重复 & 状态机修复 — 技术设计

## 问题域

HarnessPRD 前端存在三类问题：
1. **按钮双重渲染**：`reviewing_*` 状态 Sidebar 与 DocumentReview 各自渲染确认/AI优化/编辑按钮
2. **状态不一致**：三种回退入口行为不同，autoAdvance 机制与手动推进交织
3. **显示框溢出**：文档生成流式输出无高度约束，长内容撑出视口

## 技术方案

### 1. 按钮架构重构

**原则**：文档操作按钮归 DocumentReview 独管，Sidebar 仅保留进度导航。

**改动**：
- `App.tsx` `primaryActions`/`secondaryActions` 构建逻辑（~948-990行）：`reviewing_*` 状态下返回空数组
- `Sidebar.tsx`：移除底部 autoAdvance 开关 UI
- `App.tsx`：删除 `handleDocEdit`（旧 Sidebar 编辑按钮处理器）

**按钮归属表**：

| 按钮 | 归属 | 显示条件 |
|------|------|---------|
| 确认 | DocumentReview 底部 | `reviewing_*` 状态 |
| AI 优化 | DocumentReview 工具栏 | `reviewing_*` 状态 |
| 编辑 | DocumentReview 工具栏 | `reviewing_*` 状态 |
| 停止生成 | DocumentReview 工具栏 | `generating_*` 状态 + `isStreaming` |
| 上一步/下一步 | Sidebar 导航组 | `reviewing_*` 状态 |
| 生成 PRD/摘要 | Sidebar 操作组 | `ai_dialogue` 状态 |
| 开始新项目 | Sidebar 操作组 | `completed` 状态 |

### 2. 统一回退机制

**`handleGoBack(targetState: ViewState)` 实现**：

```typescript
const handleGoBack = useCallback((targetState: ViewState) => {
  const currentIdx = STEP_INDEX_MAP[viewState];
  const targetIdx = STEP_INDEX_MAP[targetState];
  if (targetIdx >= currentIdx) return; // 只允许后向

  // 计算受影响步骤
  const affectedSteps = STEPS.filter((_, i) => i > targetIdx);
  const affectedDocs = affectedSteps
    .map(s => DOC_TYPE_BY_STEP[s])
    .filter(Boolean)
    .filter(docType => project[docType].confirmed);

  if (affectedDocs.length === 0) {
    // 无受影响文档，直接切换
    switchView(targetState);
    return;
  }

  // 显示确认对话框
  showConfirmDialog({
    title: '确认回退',
    message: `回退到「${STEP_LABELS[targetState]}」将重置以下文档的确认状态：${affectedDocs.map(d => DOC_LABELS[d]).join('、')}`,
    onConfirm: () => {
      updateProject(prev => {
        const next = { ...prev };
        for (const docType of affectedDocs) {
          next[docType] = { ...next[docType], confirmed: false };
        }
        next.pendingUpdates = [...new Set([...prev.pendingUpdates, ...affectedSteps])];
        next.completedSteps = prev.completedSteps.filter(
          s => STEP_INDEX_MAP[s] <= targetIdx
        );
        next.viewState = targetState;
        setShowCompletionPrompt(false);
        return next;
      });
    },
  });
}, [viewState, project, switchView]);
```

**回退映射表**：

| 当前状态 | 可回退至 | 受影响文档 |
|---------|---------|----------|
| `generating_prd` | `ai_dialogue` | — |
| `reviewing_prd` | `ai_dialogue`, `form_editing` | PRD |
| `generating_api` | `reviewing_prd`, `ai_dialogue` | — |
| `reviewing_api` | `reviewing_prd`, `ai_dialogue` | API |
| `generating_prompts` | `reviewing_api`, `reviewing_prd`, `ai_dialogue` | — |
| `reviewing_prompts` | `reviewing_api`, `reviewing_prd`, `ai_dialogue` | Prompts |
| `completed` | `form_editing`（开始新项目） | 全部 |

### 3. 停止生成

**`handleStopGeneration` 实现**：

```typescript
const abortControllerRef = useRef<AbortController | null>(null);

const handleStopGeneration = useCallback(() => {
  abortControllerRef.current?.abort();
  const preGenState = getPreGenerationState(viewState);
  // generating_prd → ai_dialogue
  // generating_api → reviewing_prd
  // generating_prompts → reviewing_api
  handleGoBack(preGenState);
}, [viewState, handleGoBack]);
```

**AbortController 集成**：
- `generateDocumentStream` 调用前创建新 `AbortController`
- 传给 `fetch(url, { signal: abortControllerRef.current.signal })`
- `readStream` 的 `onDone` 中清除引用

### 4. 显示框修复

**DocumentReview.tsx** — 内容区容器：

```tsx
<div
  className="flex-1 overflow-y-auto px-4 py-6"
  style={{ maxHeight: 'calc(100vh - 12rem)' }}
>
```

12rem = 顶部导航栏(~4rem) + DocumentReview header(~3rem) + 底部工具栏(~3rem) + 安全边距(~2rem)

### 5. 数据迁移

**types/index.ts — `loadProject()`**：
```typescript
// 忽略旧 autoAdvance 字段
const { autoAdvance, ...cleanData } = rawData;
// 确保必要字段存在默认值
return {
  ...createDefaultProject(),
  ...cleanData,
};
```

### 6. Debug 埋点

| 函数 | 探针类型 | 记录内容 |
|------|---------|---------|
| `handleGoBack` | trace | targetState, 受影响步骤, completedSteps 变更 |
| `handleConfirmDoc` | log | docType, viewState 变更, showCompletionPrompt |
| `switchView` | trace | 每次 ViewState 转换 from → to |
| `handleStopGeneration` | log | abort 调用, 回退目标状态 |
| `generateDocumentStream` | timer | 文档生成耗时 |

回归验证通过后执行 `debug-cleanup` 移除所有探针。

## 文件改动清单

| 文件 | 改动量 | 主要修改 |
|------|--------|---------|
| `types/index.ts` | ~20行 | 移除 autoAdvance, 更新 VALID_TRANSITIONS, 数据迁移 |
| `App.tsx` | ~150行 | handleGoBack, handleStopGeneration, autoAdvance 删除, 按钮分发简化 |
| `Sidebar.tsx` | ~30行 | 移除 autoAdvance 开关, 操作按钮条件更新 |
| `DocumentReview.tsx` | ~10行 | 停止生成按钮, max-height, onStop prop |
| `CompletionPromptBar.tsx` | ~5行 | 返回按钮回调改为 handleGoBack |

## 测试策略

1. **全程遍历**：`form_editing` → `ai_dialogue` → `generating_prd` → `reviewing_prd` → `generating_api` → `reviewing_api` → `generating_prompts` → `reviewing_prompts` → `completed`，每步验证按钮状态
2. **回退验证**：从 `reviewing_prompts` 回退到 `ai_dialogue`，确认 confirmed 重置、pendingUpdates 标记、completedSteps 更新
3. **停止生成**：`generating_prd` → 点击停止 → SSE 中断 → 回到 `ai_dialogue`
4. **显示框**：长文档流式输出 → 内容区固定高度 + 内部滚动，不撑出视口
5. **数据兼容**：加载含 `autoAdvance` 的旧 localStorage 不报错
6. **按钮去重**：`reviewing_*` 状态下 Sidebar 仅有进度导航，DocumentReview 工具栏完整

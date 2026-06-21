# Brainstorm Summary

- Change: fix-buttons-and-state-flow
- Date: 2026-06-21

## 确认的技术方案

1. **按钮架构**：DocumentReview 独管文档操作按钮（确认/AI优化/编辑/停止生成），Sidebar 仅保留进度导航 + 上一步/下一步
2. **统一回退**：`handleGoBack(targetState)` 替代三种旧入口，含确认对话框 + confirmed 重置 + completedSteps 调整 + pendingUpdates
3. **移除 autoAdvance**：CompletionPromptBar 始终显示，旧数据兼容忽略 autoAdvance 字段
4. **停止生成**：AbortController abort SSE → handleGoBack 回退到生成前状态
5. **显示框**：`max-h-[calc(100vh-12rem)]` + `overflow-y-auto`
6. **Debug 埋点**：handleGoBack/switchView trace，handleConfirmDoc/handleStopGeneration log，generateDocumentStream timer → 回归通过后 debug-cleanup

## 关键取舍与风险

- **[取舍] 移除 autoAdvance 增加一次点击** → 换取确定性
- **[风险] App.tsx 1077 行手术式修改** → 严格按状态映射表逐项改，每步冒烟
- **[风险] AbortController 与 SSE readStream 协作** → 验证 done 事件
- **[风险] 回退时 confirmed 重置需用户重新确认** → 符合预期

## 测试策略

- 全程遍历 9 个 ViewState，验证每步按钮状态
- 回退场景：reviewing_prompts → ai_dialogue，验证 confirmed 重置 + pendingUpdates
- 停止生成：generating_prd → stop → ai_dialogue，验证 SSE 中断 + 回退
- 显示框：长文档生成时内容区不撑出视口
- 旧数据兼容：autoAdvance 字段不报错
- 按钮重复：reviewing_* 状态 sidebar 无操作按钮

## Spec Patch

无（所有 delta spec 已在 open 阶段创建完成）

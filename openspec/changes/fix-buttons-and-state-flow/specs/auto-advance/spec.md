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

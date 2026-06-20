## Context

HarnessPRD 当前后端使用内存 `dict[str, SessionData]` 存储会话状态，服务器重启即丢失。前端 localStorage 存了 sessionId 和文档内容作为"影子状态"，但与后端不同步。用户刷新页面可恢复（服务器活着时），但关闭重开或服务器重启后数据丢失。

当前 API 共 33 个端点，每个端点通过 session_id 查内存获取上下文。前端 App.tsx 单组件 600 行管理全部状态。

## Goals / Non-Goals

**Goals:**
- 用户刷新或关闭页面后能恢复到上次进度，包括表单、对话和已生成的文档
- 服务器重启后用户数据不丢失（前端 localStorage 持久化）
- 后端无状态，支持未来水平扩展
- API 精简，减少维护成本
- 文档生成中断后可续写

**Non-Goals:**
- 跨设备同步（localStorage 是设备本地的）
- 用户认证或多用户协作
- 数据库引入（SQLite、PostgreSQL 等）
- 文档版本历史（只保留最新版本）
- 对话消息的断点续写（对话消息短，不需要）

## Decisions

### D1: 前端 localStorage 作为唯一真相源

**选择**：前端单键 `harnessprd:project` 存储全部项目状态

**替代方案**：
- 后端文件持久化（JSON 文件）：需要文件 IO、并发锁、清理机制
- SQLite：引入数据库依赖，增加部署复杂度
- 混合方案（前后端各存一份）：同步逻辑复杂，容易不一致

**理由**：
- 无数据库约束下最简单的持久化方案
- 前端已有 localStorage 基础设施
- 单键存储避免多键不同步问题
- 5-10MB 限额对本项目绰绰有余（预估 ~106KB）

### D2: 前端生成 session_id

**选择**：前端用 `crypto.randomUUID()` 生成 session_id，后端仅用于日志

**替代方案**：
- 后端首次请求时生成并返回：需要额外请求，后端需要临时存储

**理由**：
- 前端主导架构下，session 创建不依赖后端
- 减少一次网络往返
- 后端纯被动，不需要"创建 session"的概念

### D3: 每个请求携带完整上下文

**选择**：API 请求体包含 form_data、history、previous_documents 等全部上下文

**替代方案**：
- 后端维护 session 缓存：回到有状态架构
- 前端只传增量，后端拼装：后端需要存储历史

**理由**：
- 后端真正无状态
- 请求可被任意后端实例处理
- 10 轮对话 ~5-10KB，三份文档 ~25KB，总量可控

### D4: Review 循环保留后端

**选择**：`POST /documents/{type}/optimize` 后端内部循环 review→rewrite，SSE 流式返回最终结果

**替代方案**：
- 前端控制循环（多次调用 review + rewrite 接口）：前端复杂度高，请求次数多

**理由**：
- Review→Rewrite 是原子操作，前端不需要干预每轮
- 后端循环更高效（内部调用，无网络往返）
- SSE 流式返回让用户看到进度
- P2 可视化可通过 SSE 事件扩展（`review_round` 事件）

### D5: 文档续写通过 previous_content 参数

**选择**：文档生成端点接受可选 `previous_content`，后端在 prompt 中追加续写指令

**替代方案**：
- 后端存储已生成内容，前端传 offset：后端需要状态
- 完全前端拼接：LLM 不知道上下文，续写质量差

**理由**：
- LLM 无状态，续写靠 prompt 工程
- 前端传完整已有内容，后端构造续写 prompt
- 模板增加 `{% if previous_content %}` 分支即可

### D6: API 从 33 端点精简到 8 端点

**新端点清单**：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/questions` | 表单配置（不变） |
| `POST` | `/api/chat/stream` | 对话 SSE（合并 start/continue） |
| `POST` | `/api/summary/generate` | 需求摘要生成 |
| `POST` | `/api/documents/prd/stream` | PRD 生成 SSE |
| `POST` | `/api/documents/api/stream` | 接口文档生成 SSE |
| `POST` | `/api/documents/prompts/stream` | 提示词套件生成 SSE |
| `POST` | `/api/documents/{type}/optimize` | Review→Rewrite 优化 SSE |
| `POST` | `/api/documents/{type}/download` | 下载 .md（改为 POST 传 body） |

**删除的端点**：所有 `/api/sessions/*` 路由、状态查询、确认/拒绝端点、编辑端点

## Risks / Trade-offs

**[R1] localStorage 数据丢失** → 用户清浏览器数据、换浏览器、隐私模式下数据丢失。这是 C 方案的固有取舍。缓解：提供"下载项目数据"功能（P2，不在本次范围）。

**[R2] 请求体积增大** → 每次请求携带完整上下文，网络开销增加。缓解：10 轮对话 + 三份文档预估 ~50KB，在可接受范围。超过时可考虑压缩。

**[R3] 续写质量不稳定** → LLM 续写可能有 1-2 句重复或表格断裂。缓解：模板中明确指示"不要重复已有内容"，前端可提示用户手动编辑。

**[R4] 并发请求冲突** → 用户多标签页打开同一项目，localStorage 可能冲突。缓解：单用户场景下低概率，可接受。

**[R5] 前端状态管理复杂度** → App.tsx 600 行将更臃肿。缓解：拆分为 useReducer + 自定义 hooks。

## Migration Plan

1. 先实现后端新 API（旧 API 保留并行运行）
2. 前端切换到新 API
3. 验证全流程可用
4. 删除旧 API 和 SessionStore
5. 更新文档

回滚策略：旧 API 保留到新 API 验证通过后再删除。Git 分支管理。

## Open Questions

- 前端 App.tsx 是否需要拆分为多个 hooks/useReducer？（建议是，但不在本次核心范围）
- 是否需要"导出/导入项目数据"功能？（P2，可后续迭代）

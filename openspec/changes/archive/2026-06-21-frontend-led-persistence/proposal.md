## Why

后端 SessionStore 是纯内存 dict，服务器重启后所有会话数据丢失。前端 localStorage 存了 sessionId 但后端已无此 session，用户刷新页面后被迫从头填写表单。当前架构下前后端各自维护一份"影子状态"，无法可靠恢复进度。

## What Changes

- **后端无状态化**：删除 `SessionStore` 和 `StateEnum`，后端不再存储会话数据。所有上下文由前端在每次请求中携带。
- **前端主导持久化**：localStorage 单键 `harnessprd:project` 存储全部项目状态（表单、对话、三份文档），作为唯一真相源。
- **前端生成 session_id**：前端创建 UUID，后端仅用于日志追踪，不校验是否存在。
- **API 精简**：33 个端点 → 8 个。每个请求携带完整上下文（form_data、history、documents）。
- **文档续写**：文档生成 SSE 中断后，可通过 `previous_content` 参数断点续写。
- **Review 循环保留后端**：`POST /documents/{type}/optimize` 后端内部循环 review→rewrite，流式返回最终结果。

**BREAKING**：所有 API 请求体和响应体变更。前端不再使用 `/api/sessions/*` 系列端点。

## Capabilities

### New Capabilities
- `frontend-persistence`：前端 localStorage 单键持久化、session 恢复、状态同步
- `stateless-backend`：后端无状态 API 设计、请求体携带上下文、session_id 透传日志
- `document-resume`：文档生成断点续写、previous_content 参数、模板续写支持

### Modified Capabilities
（无现有 spec 需要修改）

## Impact

- **后端删除**：`core/state.py`（SessionStore、StateEnum）、`services/session_service.py`（大部分逻辑）、`api/sessions.py`（全部路由）
- **后端重写**：`api/conversation.py`、`api/documents.py`、`services/conversation_service.py`、`services/document_service.py`
- **前端重写**：`App.tsx`（状态管理）、`services/api.ts`（新 API 契约）、`types/index.ts`（新类型）
- **模板修改**：`prompts/generate_prd.jinja2` 等 3 个生成模板增加 `previous_content` 支持
- **依赖**：无新增依赖

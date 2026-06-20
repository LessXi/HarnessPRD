## 1. 后端新 API 端点（P0）

- [x] 1.1 创建 `backend/api/schemas.py` 新请求模型：`ChatRequest`、`SummaryRequest`、`DocumentRequest`、`OptimizeRequest`，字段与 design.md D6 对齐
- [x] 1.2 重写 `backend/api/conversation.py`：实现 `POST /api/chat/stream`（合并 start/continue），从请求体读取 history 和 form_data，调用 ConversationService 流式返回
- [x] 1.3 重写 `backend/api/documents.py`：实现 `POST /api/documents/{type}/stream` 和 `POST /api/documents/{type}/optimize`，从请求体读取上下文
- [x] 1.4 实现 `POST /api/summary/generate` 端点，从请求体读取 history 和 form_data
- [x] 1.5 保留 `GET /api/questions` 和 `POST /api/documents/{type}/download` 端点（下载端点改为从请求体读取内容）

验收标准：所有新端点可独立调用，不依赖任何内存存储 ✓

## 2. 后端 Service 层改造（P0）

- [x] 2.1 重写 `backend/services/conversation_service.py`：`start_conversation_stream` 和 `continue_conversation_stream` 合并为单一方法，从参数接收 history 和 form_data，不查 session
- [x] 2.2 重写 `backend/services/document_service.py`：`generate_*_stream` 从参数接收上下文（form_data、requirements_summary、previous_content），不查 session
- [x] 2.3 修改 `backend/services/document_service.py` 的 `optimize_document_stream`：从参数接收 content 和上下文，不查 session
- [x] 2.4 更新 `backend/services/llm_service.py`：确认 `stream_generate` 和 `stream_chat` 签名不变，仅调整调用方传参方式

验收标准：所有 service 方法从参数获取数据，不引用 session_store ✓

## 3. 后端续写支持（P0）

- [x] 3.1 修改 `backend/prompts/generate_prd.jinja2`：增加 `{% if previous_content %}` 分支，追加续写指令
- [x] 3.2 修改 `backend/prompts/generate_api.jinja2`：同上
- [x] 3.3 修改 `backend/prompts/generate_prompts.jinja2`：同上
- [x] 3.4 在 `DocumentRequest` 模型中添加 `previous_content: str = ""` 字段
- [x] 3.5 在 `_generate_document_stream` 中将 `previous_content` 传入模板渲染

验收标准：传入 previous_content 时，LLM 从断点续写，不重复已有内容 ✓

## 4. 后端清理旧代码（P0）

- [x] 4.1 删除 `backend/api/sessions.py` 中除 `/questions` 外的所有路由
- [x] 4.2 删除 `backend/core/state.py` 中的 `SessionStore` 类和 `session_store` 单例
- [x] 4.3 删除 `backend/core/state.py` 中的 `StateEnum` 枚举
- [x] 4.4 精简 `backend/services/session_service.py`：仅保留 `_validate_form` 和 `_load_questions`，删除 session CRUD 方法
- [x] 4.5 更新 `backend/main.py`：移除旧路由挂载，保留 questions 端点
- [x] 4.6 更新 `backend/api/schemas.py`：删除旧的 `SessionCreatedResponse`、`SessionSummary`、`ConfirmResponse` 等模型

验收标准：后端无 SessionStore、无 StateEnum、无内存 session 存储 ✓

## 5. 前端类型定义（P0）

- [x] 5.1 更新 `frontend/src/types/index.ts`：新增 `ProjectState`、`DocumentState` 接口，与后端 Pydantic 模型字段对齐
- [x] 5.2 新增 `ChatRequest`、`SummaryRequest`、`DocumentRequest`、`OptimizeRequest` TypeScript 类型
- [x] 5.3 删除不再需要的类型（如旧的 session 相关类型）

验收标准：TypeScript 类型与后端请求模型字段完全一致 ✓

## 6. 前端 API 层重写（P0）

- [x] 6.1 重写 `frontend/src/services/api.ts`：实现 `chatStream` 函数，发送 `ChatRequest`，返回 SSE 流
- [x] 6.2 实现 `generateSummary` 函数，发送 `SummaryRequest`
- [x] 6.3 实现 `generateDocumentStream` 函数，发送 `DocumentRequest`，支持 previous_content
- [x] 6.4 实现 `optimizeDocumentStream` 函数，发送 `OptimizeRequest`
- [x] 6.5 保留 `getQuestions` 和 `downloadDocument` 函数
- [x] 6.6 删除旧的 `createSession`、`sendMessage`、`getMessages`、`startConversationStream`、`continueConversationStream` 等函数

验收标准：API 层仅包含新端点的调用函数 ✓

## 7. 前端状态管理重构（P0）

- [x] 7.1 重写 `frontend/src/App.tsx` 状态结构：使用 `ProjectState` 接口，单键 `harnessprd:project` 存储
- [x] 7.2 实现 `loadProject()` 函数：从 localStorage 读取项目状态，无数据时返回初始状态
- [x] 7.3 实现 `saveProject(state)` 函数：将项目状态写入 localStorage
- [x] 7.4 在每个状态变更点调用 `saveProject`：表单提交、对话消息、文档生成完成、viewState 变化
- [x] 7.5 修改表单提交逻辑：前端生成 session_id（`crypto.randomUUID()`），调用 `chatStream` 而非 `createSession`
- [x] 7.6 修改对话逻辑：调用 `chatStream`，传入完整 history，不再区分 start/continue

验收标准：刷新页面后恢复到上次 viewState，对话和文档内容完整保留 ✓

## 8. 前端续写 UI（P1）

- [x] 8.1 在 `DocumentReview` 组件中添加"继续生成"按钮：SSE 中断时显示
- [x] 8.2 实现续写逻辑：调用 `generateDocumentStream`，传入 `previous_content` 为当前 content
- [x] 8.3 续写完成后将新内容追加到已有 content 后面
- [x] 8.4 处理续写中断：允许多次续写，每次传入最新完整内容

验收标准：文档生成中断后可点击"继续生成"，内容从断点处续写 ✓

## 9. 文档编辑功能修复（P1）

- [x] 9.1 修复 `DocumentReview.tsx` 中 textarea 的 `readOnly` 属性：改为可编辑
- [x] 9.2 实现编辑保存：前端直接更新 localStorage
- [x] 9.3 编辑后的内容在续写时作为 previous_content 传入

验收标准：用户可手动编辑文档内容，编辑后可继续 AI 优化 ✓

## 10. 更新项目文档（P2）

- [x] 10.1 更新 `AGENTS.md`：反映新的无状态架构和 API 端点
- [x] 10.2 更新 `docs/api-endpoints.md`：新端点清单
- [x] 10.3 更新 `docs/state-machine.md`：移除后端状态机描述，改为前端 viewState 说明
- [x] 10.4 更新 `docs/session-data-structure.md`：改为 ProjectState 结构说明

验收标准：文档与代码实现一致 ✓

## Post-Review Fixes

- [x] 修复 `App.tsx` 中 6 处 `DocumentReview` 缺失 `docType` prop（下载按钮不渲染）
- [x] 更新 `backend/tests/conftest.py` — 移除 SessionData/session_store，新增 mock_form_dict/mock_history
- [x] 重写 `backend/tests/test_conversation_pure.py` — 匹配新函数签名（`_form_to_kwargs`、`_build_system_prompt`、`_build_lc_messages`）
- [x] 重写 `backend/tests/test_services.py` — 匹配新签名（`_validate_form` 接受 dict、`_build_prompt_kwargs` 接受 kwargs）
- [x] 精简 `backend/tests/test_routes.py` — 旧路由测试标记 skip，保留 Health/Questions 测试

**测试结果**：34 passed, 0 failed

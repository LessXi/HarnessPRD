# Comet Design Handoff

- Change: debug-observability
- Phase: design
- Mode: compact
- Context hash: b57e5abe7cc690f9ade583c06103594e3624c6227b621cae1ea0618df21afffe

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/debug-observability/proposal.md

- Source: openspec/changes/debug-observability/proposal.md
- Lines: 1-39
- SHA256: 4349ffc9e6006d29288a67464f03046da25ee75a5e110013f2df6c60937695a8

```md
## Why

HarnessPRD 当前缺少可观测性体系：LLM 调用无追踪、日志零散、无请求链路关联。AI debug 时需在多处 grep 猜测因果链，排查效率低。项目已过 v1 原型阶段（10 个 viewState、Review→Rewrite 循环、多文档生成），流程复杂度需要配套的 AI 可消费 debug 基础设施。

## What Changes

- **新增 LangSmith 集成**：所有 LLM 调用自动上报 trace（prompt/response/token/latency），metadata 携带 session_id 和 doc_type
- **新增 loguru 结构化日志**：替换 Python logging，终端彩色输出 + NDJSON 文件（按天轮转），correlation_id 贯穿全链路
- **新增请求拦截中间件**：FastAPI middleware 记录所有 API 请求的 method/path/耗时/状态码
- **新增 Prompt 渲染追踪**：Jinja2 渲染后的实际 prompt 写入日志（可配置截断长度）
- **新增错误分级与分类**：LLM 错误（rate_limit/timeout/content_filter）/ HTTP 错误 / 业务错误自动分类
- **新增 Debug 诊断端点**：`GET /api/debug/session/{id}` 返回 session 完整诊断数据
- **新增动态日志级别**：`POST /api/debug/log-level` 运行时调整
- **新增启动配置校验**：LangSmith 连通性/API key 有效性/日志目录可写自检
- **新增前端日志上报**：SSE 事件 + viewState 转换自动 POST 到 `/api/debug/log`
- **新增 `.env` 配置项**：`LANGCHAIN_TRACING_V2`、`LANGCHAIN_API_KEY`、`LANGCHAIN_PROJECT`、`LOG_LEVEL`，全部可控关闭

## Capabilities

### New Capabilities

- `llm-observability`: LangSmith 追踪所有 LLM 调用，Prompt 渲染内容追踪，trace metadata 携带 session_id/doc_type
- `structured-logging`: loguru 结构化日志（终端彩色 + NDJSON 文件），请求拦截中间件，错误分级分类，correlation_id 全链路关联
- `debug-api`: GET /api/debug/session/{id} 诊断端点、POST /api/debug/log-level 动态调级、启动配置校验与自检
- `frontend-debug-logging`: 前端 SSE 事件日志、viewState 转换日志、批量 POST 到后端 debug 端点

### Modified Capabilities

<!-- 无现有 capability 被修改 — 全部为新增 -->

## Impact

- **依赖新增**: `langsmith`、`loguru` 加入 `backend/requirements.txt`
- **配置变更**: `backend/.env.example` 新增 4 个配置项
- **后端新增文件**: `core/logging_config.py`、`core/middleware.py`、`core/error_classifier.py`、`api/debug.py`
- **后端修改文件**: `config.py`、`main.py`、`llm_service.py`、`conversation_service.py`、`document_service.py`
- **前端新增文件**: `utils/debugLogger.ts`
- **前端修改文件**: `utils/api.ts`、`store/useProjectStore.ts`
- **非目标**: 不修改现有业务逻辑、不改变 SSE 协议、不引入新数据库/缓存依赖
```

## openspec/changes/debug-observability/design.md

- Source: openspec/changes/debug-observability/design.md
- Lines: 1-105
- SHA256: e0e8b998e8e30d7cb509c27cdf74f1e35d4f78527b5e10e76229d1f317410672

[TRUNCATED]

```md
## Context

HarnessPRD 当前使用 Python `logging` 模块仅做启动警告，无 LLM 调用追踪、无请求链路关联、无结构化日志。前端日志仅 `console.error` 零散分布。当 AI 需要排查问题时，缺少一条 `correlation_id` 贯穿全链路的数据支撑。

**约束**：
- 后端无数据库、无认证、无 Redis — debug 数据仅内存暂存
- LangChain 0.3.x 原生支持 `langsmith` callback 环境变量注入
- SSE 流式传输不改变协议
- 前端 React 18 + Zustand 状态管理，`localStorage` 持久化

## Goals / Non-Goals

**Goals:**
- 所有 LLM 调用通过 LangSmith 自动上报 trace
- loguru 替换 Python logging，终端彩色 + NDJSON 文件双输出
- 一条 `correlation_id` 贯穿 API 请求 → LLM 调用 → SSE → 前端，AI 可快速关联
- 请求拦截中间件记录所有 API 的 method/path/耗时/状态码
- Prompt 渲染后内容可配置写入日志，辅助 AI debug prompt engineering
- LLM 错误自动分类（rate_limit/timeout/content_filter），AI 按类别路由排查
- `GET /api/debug/session/{id}` 一键拉取 session 全量诊断数据
- 运行时 `POST /api/debug/log-level` 动态调整日志级别
- 启动时自检 LangSmith 连通性和日志目录可写性

**Non-Goals:**
- 不提供前端可视化 debug 面板
- 不做 LangSmith feedback/annotation（预留 metadata 扩展点）
- 不做 SSE chunk 数/字节统计
- 不做生产级日志聚合/采集
- 不修改现有业务逻辑或 SSE 协议格式

## Decisions

### D1: LangSmith 接入方式 — 环境变量 + LangChain callback

**选择**：通过 `LANGCHAIN_TRACING_V2=true` 环境变量 + `langsmith` SDK 的 `tracing_v2_enabled()` 自动注入 LangChain callback。

**备选**：手动在代码中创建 `LangSmithTracer` 实例并传入每个 `llm.astream()` 的 `config` 参数。

**理由**：环境变量方式零代码侵入，LangChain 0.3 原生支持，关闭只需改 `.env`。手动方式需要修改 5 处 LLM 调用点，且容易遗漏。自定义 run name 和 metadata 通过 `langsmith.run_helpers.trace()` context manager 补充。

### D2: loguru 配置 — 拦截标准 logging + 双输出

**选择**：loguru 通过 `logger.add()` 配置双 sink（`sys.stderr` 彩色 + `logs/app_{time:YYYY-MM-DD}.ndjson` 结构化），使用 `logging.basicConfig(handlers=[InterceptHandler()])` 拦截标准库 logging 到 loguru。

**备选**：structlog 在已有 logging 基础上渐进增强。

**理由**：loguru API 简洁（`logger.info("msg")` 一行），天然支持彩色终端、NDJSON 序列化、文件轮转。用户已选择 loguru。

### D3: correlation_id 贯穿策略

**选择**：FastAPI middleware 从请求头 `X-Correlation-ID` 提取，若无则生成 UUID4。存储在 `request.state.correlation_id`，通过 `ContextVar` 传递给 loguru 的 `logger.bind(corr_id=...)`。前端在每个 debug 上报中携带 `session_id` 作为 correlation_id。

**备选**：使用 Python `logging` 的 `LogRecord` extra 字段传递。

**理由**：`ContextVar` 是 asyncio 原生协程安全方案。loguru 的 `bind()` 方法天然支持结构化上下文字段。

### D4: Prompt 渲染追踪 — Jinja2 wrapper

**选择**：在 `llm_service.py` 的 `load_prompt()` 函数中，渲染后通过 loguru logger 写入日志，level 为 `DEBUG`。截断长度由 `config.PROMPT_LOG_MAX_LENGTH`（默认 2000 字符）控制。

**备选**：在 LangChain callback 的 `on_llm_start` 中捕获 prompt。

**理由**：LangChain callback 的 prompt 是 LangChain message 对象，不如 Jinja2 渲染后的实际文本直观。wrapper 方式在最源头拿到最终 prompt 文本。

### D5: 错误分类架构

**选择**：定义 `ErrorCategory` enum（`LLM_RATE_LIMIT`、`LLM_TIMEOUT`、`LLM_CONTENT_FILTER`、`LLM_UNKNOWN`、`HTTP_CLIENT_ERROR`、`HTTP_SERVER_ERROR`、`BUSINESS`、`UNKNOWN`），通过 `classify_error(exception) -> ErrorCategory` 函数基于异常类型和消息模式匹配分类。

**备选**：依赖 LangSmith 的错误分类。

**理由**：LangSmith 分类粒度不够细，且关闭 LangSmith 后需独立分类能力。

### D6: Debug API 端点设计

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/debug/log` | POST | 前端批量上报日志 |
| `/api/debug/session/{session_id}` | GET | 返回 session 诊断数据 |
| `/api/debug/log-level` | POST | 动态调整日志级别 |

```

Full source: openspec/changes/debug-observability/design.md

## openspec/changes/debug-observability/tasks.md

- Source: openspec/changes/debug-observability/tasks.md
- Lines: 1-55
- SHA256: 115e003ad008554a94f72d58e42010944b872395234a3bbc011e7e8b63fec392

```md
## 1. 依赖与配置 (P0)

- [ ] 1.1 添加 `langsmith`、`loguru` 到 `backend/requirements.txt`，`pip install`
- [ ] 1.2 在 `backend/.env.example` 中添加 `LANGCHAIN_TRACING_V2`、`LANGCHAIN_API_KEY`、`LANGCHAIN_PROJECT`、`LOG_LEVEL`、`PROMPT_LOG_MAX_LENGTH` 配置项及注释
- [ ] 1.3 在 `backend/core/config.py` 的 `Settings` 类中添加对应字段及校验逻辑（`check_langsmith_config` validator：tracing 开启时 api_key 缺失仅 WARNING）

## 2. loguru 日志核心 (P0)

- [ ] 2.1 创建 `backend/core/logging_config.py`：配置 loguru 双 sink（终端彩色 `sys.stderr` + NDJSON 文件 `logs/app_{time:YYYY-MM-DD}.ndjson`，rotation 每日，retention 7 天），实现 `InterceptHandler` 桥接标准 logging
- [ ] 2.2 在 `backend/main.py` 的 app 创建后调用 `setup_logging()`，替换 uvicorn 默认 logging，启动时输出初始化日志
- [ ] 2.3 在 `backend/core/logging_config.py` 中实现 `get_logger(name)` 工厂函数，返回绑定了模块名的 loguru logger

## 3. 请求中间件与错误分类 (P0)

- [ ] 3.1 创建 `backend/core/middleware.py`：实现 `RequestLoggingMiddleware`（ASGI middleware），记录 method/path/status/duration_ms/corr_id，读取/生成 `X-Correlation-ID` 头
- [ ] 3.2 在 `backend/main.py` 的 CORS middleware 之后注册 `RequestLoggingMiddleware`
- [ ] 3.3 创建 `backend/core/error_classifier.py`：定义 `ErrorCategory` enum 和 `classify_error(exception) -> ErrorCategory` 函数，覆盖 OpenAI/Anthropic/DeepSeek 的 rate_limit/timeout/content_filter 异常类型

## 4. LangSmith 集成与 Prompt 追踪 (P0)

- [ ] 4.1 在 `backend/core/config.py` 或 `main.py` 的 startup 事件中根据 `LANGCHAIN_TRACING_V2` 调用 `langsmith.tracing_v2_enabled()` 开启/关闭追踪
- [ ] 4.2 修改 `backend/services/llm_service.py`：在 `stream_chat`、`stream_generate` 和 `get_llm` 调用链中注入 LangSmith metadata（`run_name`、`tags`、`metadata.session_id`、`metadata.doc_type`）— 通过 `langsmith.run_helpers.trace()` 或 `RunnableConfig`
- [ ] 4.3 修改 `backend/services/llm_service.py` 的 `load_prompt()`：在 `LOG_LEVEL=DEBUG` 时通过 loguru 记录渲染后的 prompt 文本（截断 `PROMPT_LOG_MAX_LENGTH`），写入 NDJSON
- [ ] 4.4 修改 `backend/services/conversation_service.py` 和 `backend/services/document_service.py`：在所有 LLM 调用点（`chat_stream`、`generate_summary`、`generate_document_stream`、`optimize_document_stream`、`_call_llm_once`）添加结构化日志（`logger.bind(corr_id=...)`），记录调用的 doc_type/phase，异常时调用 `classify_error()` 分类

## 5. 启动配置校验 (P1)

- [ ] 5.1 在 `backend/main.py` 的 startup 事件中实现 `validate_debug_config()`：检查 LangSmith API key 非空（若 tracing 开启）、ping `api.smith.langchain.com`（5s 超时）、检查 `backend/logs/` 目录可写
- [ ] 5.2 失败场景输出 WARNING 日志，不阻塞启动

## 6. Debug API 端点 (P1)

- [ ] 6.1 创建 `backend/api/debug.py`：定义 Pydantic 请求模型（`LogEntry`、`BatchLogRequest`、`LogLevelRequest`），实现 `POST /api/debug/log` 接收前端批量日志并存入内存 `debug_store: OrderedDict`
- [ ] 6.2 实现 `GET /api/debug/session/{session_id}`，聚合该 session 下的 `requests`、`llm_calls`、`sse_events`、`frontend_logs`、`errors` 返回 JSON
- [ ] 6.3 实现 `POST /api/debug/log-level`，接收 `{"level": "..."}`，调用 `logger.remove()` + `logger.add()` 动态调整级别
- [ ] 6.4 在 `backend/main.py` 注册 `debug_router`，挂载到 `/api/debug` 前缀

## 7. 前端 debugLogger 工具 (P1)

- [ ] 7.1 创建 `frontend/src/utils/debugLogger.ts`：单例 `debugLogger`，维护内存 buffer（max 100 条），`log(source, data)` 方法，5 秒定时器 + buffer 满 50 条时批量 POST `/api/debug/log`（body: `{session_id, logs}`）
- [ ] 7.2 实现 `pagehide`/`beforeunload` 事件监听，使用 `navigator.sendBeacon()` flush 剩余日志
- [ ] 7.3 实现 `isEnabled()` 检查（读取 localStorage 或 env var 中的 `VITE_DEBUG_ENABLED`），关闭时所有 `log()` 调用为 no-op

## 8. 前端日志集成 (P1)

- [ ] 8.1 修改 `frontend/src/utils/api.ts` 的 `readStream()`：在 chunk/done/error 事件处理中调用 `debugLogger.log("sse:readStream", {event_type, chunk_count?, ...})`
- [ ] 8.2 修改 `frontend/src/store/useProjectStore.ts`：在 `viewState` 变更处调用 `debugLogger.log("state:transition", {from, to, trigger})`

## 9. E2E 验证 (P2)

- [ ] 9.1 验证 LangSmith trace：启动后端，调用一次 `/api/chat/stream`，确认 LangSmith dashboard 中出现 trace 且 metadata 含 session_id
- [ ] 9.2 验证 NDJSON 日志：检查 `backend/logs/app_{date}.ndjson` 包含请求日志、LLM 调用日志、错误分类日志
- [ ] 9.3 验证前端上报：打开前端 → 填写表单 → 对话 → 生成文档，确认 `GET /api/debug/session/{id}` 返回完整诊断数据
- [ ] 9.4 验证动态调级：`POST /api/debug/log-level {"level":"DEBUG"}`，确认终端日志即变为 DEBUG 级别
- [ ] 9.5 验证关闭 LangSmith：设置 `LANGCHAIN_TRACING_V2=false`，重启后端，确认 LLM 调用正常且无 LangSmith 报错
```

## openspec/changes/debug-observability/specs/debug-api/spec.md

- Source: openspec/changes/debug-observability/specs/debug-api/spec.md
- Lines: 1-42
- SHA256: 0870df8245de086e60a5332857279df4ac36e7a55fb55ace44773177bfe17bf9

```md
## ADDED Requirements

### Requirement: Session 诊断端点
系统 SHALL 提供 `GET /api/debug/session/{session_id}` 端点，返回该 session 的完整诊断数据：请求记录、LLM 调用摘要、SSE 事件序列、前端日志列表、错误列表。

#### Scenario: 获取已存在 session 的诊断数据
- **WHEN** 客户端请求 `GET /api/debug/session/abc-123`，且该 session 已产生诊断数据
- **THEN** 返回 JSON 包含 `session_id`、`requests`（请求列表）、`llm_calls`（LLM 调用摘要）、`sse_events`（SSE 事件列表）、`frontend_logs`（前端日志）、`errors`（错误列表）

#### Scenario: 获取不存在 session 的诊断数据
- **WHEN** 客户端请求 `GET /api/debug/session/nonexistent`
- **THEN** 返回 404，错误消息说明 session 无诊断数据

#### Scenario: 诊断数据自动汇聚
- **WHEN** 同一 `correlation_id` 关联的多个请求（如对话 + 摘要生成 + 文档生成）先后发生
- **THEN** `GET /api/debug/session/{id}` 返回所有这些请求的聚合数据，按时间排序

### Requirement: 动态日志级别调整
系统 SHALL 提供 `POST /api/debug/log-level` 端点，接收 `{"level": "DEBUG" | "INFO" | "WARNING" | "ERROR"}`，运行时调整 loguru 日志级别。

#### Scenario: 动态开启 DEBUG 级别
- **WHEN** 客户端 `POST /api/debug/log-level` 携带 `{"level": "DEBUG"}`
- **THEN** 终端和文件日志立即开始输出 DEBUG 级别日志，返回 `{"previous_level": "...", "current_level": "DEBUG"}`

#### Scenario: 无效级别被拒绝
- **WHEN** 客户端发送 `{"level": "TRACE"}` 或非法值
- **THEN** 返回 422，错误消息说明有效级别为 DEBUG/INFO/WARNING/ERROR

### Requirement: 启动配置校验与自检
系统 SHALL 在 FastAPI startup 事件中校验 debug 相关配置，发现问题时输出 WARNING 日志而不阻塞启动。

#### Scenario: LangSmith API Key 缺失时警告
- **WHEN** `LANGCHAIN_TRACING_V2=true` 但 `LANGCHAIN_API_KEY` 为空
- **THEN** startup 输出 WARNING：“LANGCHAIN_TRACING_V2 已启用但 LANGCHAIN_API_KEY 未配置，trace 将不上报”

#### Scenario: LangSmith 不可达时警告
- **WHEN** `LANGCHAIN_TRACING_V2=true` 但 `https://api.smith.langchain.com` 5 秒内无响应
- **THEN** startup 输出 WARNING：“LangSmith API 不可达，请检查网络或 API key”，应用继续启动

#### Scenario: 日志目录不可写时警告
- **WHEN** `backend/logs/` 目录不存在且无法创建
- **THEN** startup 输出 ERROR：“日志目录 backend/logs/ 不可写”，应用继续启动但日志仅输出到终端
```

## openspec/changes/debug-observability/specs/frontend-debug-logging/spec.md

- Source: openspec/changes/debug-observability/specs/frontend-debug-logging/spec.md
- Lines: 1-50
- SHA256: d71306371ee195821c03438aa62cc97f5a189ffd4d71a5da7cbd1f52ded4333d

```md
## ADDED Requirements

### Requirement: SSE 事件日志自动上报
前端 SHALL 在 SSE 流式消费过程中自动记录 `chunk`、`done`、`error` 事件，携带 `session_id`、`event_type`、`chunk_count`（chunk 序号，仅 chunk 事件）、`timestamp`，并通过 debugLogger 批量上报到 `POST /api/debug/log`。

#### Scenario: SSE chunk 事件上报
- **WHEN** `readStream()` 收到一个 `data: {"event":"chunk","content":"..."}` 事件
- **THEN** debugLogger 记录 `{source: "sse:readStream", event_type: "chunk", chunk_count: N}` 并加入上报 buffer

#### Scenario: SSE done 事件上报
- **WHEN** `readStream()` 收到 `data: {"event":"done"}` 事件
- **THEN** debugLogger 记录 `{source: "sse:readStream", event_type: "done", total_chunks: N}` 并立即 flush buffer

#### Scenario: SSE error 事件上报
- **WHEN** `readStream()` 收到 `data: {"event":"error",...}` 事件
- **THEN** debugLogger 记录 `{source: "sse:readStream", event_type: "error", error_content: "..."}`，日志级别为 ERROR

#### Scenario: 日志级别为 ERROR 时不上报
- **WHEN** 前端读取到的 `LOG_LEVEL` 为 ERROR（或 debug 模式关闭）
- **THEN** SSE 事件不触发日志记录和上报

### Requirement: 状态转换日志自动上报
前端 SHALL 在 `viewState` 发生变化时自动记录状态转换日志，携带 `from_state`、`to_state`、`trigger`（触发原因）、`timestamp`、`session_id`，并通过 debugLogger 上报。

#### Scenario: 用户触发的状态转换被记录
- **WHEN** 用户提交表单，`viewState` 从 `form_editing` 变为 `ai_dialogue`
- **THEN** debugLogger 记录 `{source: "state:transition", from: "form_editing", to: "ai_dialogue", trigger: "user_submit_form"}`

#### Scenario: 系统触发的状态转换被记录
- **WHEN** SSE `done` 事件触发 `viewState` 从 `generating_prd` 变为 `reviewing_prd`
- **THEN** debugLogger 记录 `{source: "state:transition", from: "generating_prd", to: "reviewing_prd", trigger: "sse_done_event"}`

#### Scenario: 状态转换序列可回溯
- **WHEN** 在 debug 诊断端点查询 session 的 `frontend_logs`
- **THEN** 状态转换日志按时序排列，完整展示状态机流转路径

### Requirement: 批量上报机制
debugLogger SHALL 维护内存 buffer（最多 100 条），每 5 秒或 buffer 满 50 条时，将缓冲日志批量 POST 到 `/api/debug/log`。批量请求体为 `{"session_id": "...", "logs": [...]}`。

#### Scenario: 定期批量上报
- **WHEN** buffer 中有 30 条日志且距上次上报已过 5 秒
- **THEN** debugLogger 发送 POST `/api/debug/log`，请求体包含 30 条日志，发送后清空 buffer

#### Scenario: Buffer 满时立即上报
- **WHEN** buffer 达到 100 条上限
- **THEN** debugLogger 立即发送 POST 请求（不等待 5 秒），发送后清空 buffer

#### Scenario: 页面关闭前 flush
- **WHEN** 用户关闭或刷新页面（`beforeunload` 事件）
- **THEN** debugLogger 使用 `navigator.sendBeacon()` 发送剩余日志，确保不丢失
```

## openspec/changes/debug-observability/specs/llm-observability/spec.md

- Source: openspec/changes/debug-observability/specs/llm-observability/spec.md
- Lines: 1-39
- SHA256: 20c2538861b1a66ca79ebc57ab4efc1eed10d3ca293eeccad6b382a955810236

```md
## ADDED Requirements

### Requirement: LangSmith 自动追踪 LLM 调用
系统 SHALL 在 `LANGCHAIN_TRACING_V2=true` 时自动将所有 LangChain LLM 调用上报至 LangSmith，包含 prompt、response、token 用量和延迟。metadata SHALL 携带 `session_id` 和 `doc_type`。

#### Scenario: 对话流式调用被追踪
- **WHEN** 用户发起 AI 对话，调用 `POST /api/chat/stream`
- **THEN** LangSmith dashboard 中出现该调用的 trace，metadata 包含 `session_id` 和 `doc_type: "chat"`

#### Scenario: 文档生成调用被追踪
- **WHEN** 系统调用 `POST /api/documents/prd/stream` 生成 PRD
- **THEN** LangSmith trace 的 metadata 包含 `doc_type: "prd"` 和对应的 `session_id`

#### Scenario: Review→Rewrite 循环被追踪
- **WHEN** 系统执行 `POST /api/documents/prd/optimize` 的 Review 调用（非流式）
- **THEN** LangSmith trace 显示 Review 调用的完整 prompt/response，metadata 标记 `phase: "review"`

#### Scenario: 流式调用多次 chunk 时 metadata 不重复
- **WHEN** `astream()` 流式返回多个 chunk（如 47 个 chunk）
- **THEN** LangSmith 中该次调用仅产生 1 条 trace，metadata 不因多次 yield 而重复

#### Scenario: LangSmith 关闭时正常运行
- **WHEN** `LANGCHAIN_TRACING_V2=false` 或 `LANGCHAIN_API_KEY` 为空
- **THEN** 所有 LLM 调用正常工作，不上报 trace，不产生错误日志

### Requirement: Prompt 渲染内容可追踪
系统 SHALL 在 `LOG_LEVEL=DEBUG` 时将 Jinja2 渲染后的实际 prompt 文本写入 NDJSON 日志文件，截断长度由 `PROMPT_LOG_MAX_LENGTH` 控制。

#### Scenario: DEBUG 级别记录完整 prompt
- **WHEN** `LOG_LEVEL=DEBUG` 且 LLM 调用 `load_prompt("backend/prompts/generate_prd.jinja2", ...)`
- **THEN** `backend/logs/app_{date}.ndjson` 中包含一条 `event: "prompt_rendered"` 记录，`detail.prompt_name` 为模板名，`detail.prompt_text` 为渲染后内容（截断后）

#### Scenario: INFO 级别不记录 prompt
- **WHEN** `LOG_LEVEL=INFO` 且发生 LLM 调用
- **THEN** 日志中不出现 `event: "prompt_rendered"` 记录

#### Scenario: Prompt 超长截断
- **WHEN** 渲染后的 prompt 文本超过 `PROMPT_LOG_MAX_LENGTH`（默认 2000 字符）
- **THEN** 日志中 `detail.prompt_text` 截断至该长度，`detail.truncated` 标记为 `true`
```

## openspec/changes/debug-observability/specs/structured-logging/spec.md

- Source: openspec/changes/debug-observability/specs/structured-logging/spec.md
- Lines: 1-58
- SHA256: 545c6c47b89730e537e1e54729fb1d0e7460b74ec2a14dad15a596df8651ce18

```md
## ADDED Requirements

### Requirement: loguru 替换 Python logging
系统 SHALL 使用 loguru 作为日志库，配置双 sink：终端彩色输出（`sys.stderr`）和 NDJSON 文件（`backend/logs/app_{time:YYYY-MM-DD}.ndjson`）。文件按天轮转，保留最近 7 天。标准库 logging 通过 `InterceptHandler` 桥接到 loguru。

#### Scenario: 终端彩色日志输出
- **WHEN** 系统启动并处理请求
- **THEN** 终端输出包含时间戳、日志级别（带颜色）、模块名、correlation_id 的格式化日志

#### Scenario: NDJSON 文件写入
- **WHEN** 任何 `logger.info()` 或 `logger.error()` 调用发生
- **THEN** `backend/logs/app_{当日日期}.ndjson` 文件中追加一条 NDJSON 行，包含 `ts`、`level`、`corr_id`、`module`、`event`、`detail` 字段

#### Scenario: 日志文件按天轮转
- **WHEN** 日期变更（跨 00:00）
- **THEN** 新日志写入新文件 `app_{新日期}.ndjson`，旧文件保留

#### Scenario: 旧日志文件自动清理
- **WHEN** logs 目录下存在超过 7 天的 `.ndjson` 文件
- **THEN** 系统启动时自动删除过期文件

#### Scenario: uvicorn 日志不丢失
- **WHEN** uvicorn 输出启动信息或访问日志
- **THEN** 这些日志通过 `InterceptHandler` 桥接到 loguru，保持原有格式和级别

### Requirement: 请求拦截中间件记录 API 调用
系统 SHALL 通过 FastAPI middleware 记录每个 HTTP 请求的 method、path、耗时（毫秒）、响应状态码和 correlation_id。

#### Scenario: 成功请求被记录
- **WHEN** 客户端发起 `POST /api/chat/stream` 并成功返回 200
- **THEN** NDJSON 日志中出现 `event: "request"` 记录，`detail.method: "POST"`，`detail.path: "/api/chat/stream"`，`detail.status: 200`，`detail.duration_ms` 为实际耗时

#### Scenario: 失败请求被记录
- **WHEN** 客户端发起请求导致 500 错误
- **THEN** 日志中出现 `event: "request"` 记录，`detail.status: 500`，日志级别为 ERROR

#### Scenario: correlation_id 自动生成
- **WHEN** 请求头中不包含 `X-Correlation-ID`
- **THEN** 中间件自动生成 UUID4 作为 `correlation_id`，并在响应头中返回 `X-Correlation-ID`

#### Scenario: correlation_id 透传
- **WHEN** 请求头包含 `X-Correlation-ID: abc-123`
- **THEN** 该请求及所有下游 LLM 调用使用同一 `correlation_id`

### Requirement: 错误分级与分类
系统 SHALL 自动对异常进行分类：LLM 错误（rate_limit、timeout、content_filter、unknown）、HTTP 错误（4xx、5xx）、业务错误。分类结果写入日志 `detail.error_category` 字段。

#### Scenario: OpenAI rate limit 错误被分类
- **WHEN** LangChain 抛出 `openai.RateLimitError`
- **THEN** 日志中 `detail.error_category: "LLM_RATE_LIMIT"`，日志级别为 WARNING

#### Scenario: LLM 超时被分类
- **WHEN** LLM 调用超过默认超时时间
- **THEN** 日志中 `detail.error_category: "LLM_TIMEOUT"`，`detail.timeout_seconds` 为实际超时阈值

#### Scenario: 未知异常被归为 UNKNOWN
- **WHEN** 发生无法匹配已知分类的异常
- **THEN** 日志中 `detail.error_category: "UNKNOWN"`，`detail.exception_type` 为异常类名
```


## 1. 依赖与配置 (P0)

- [x] 1.1 添加 `langsmith`、`loguru` 到 `backend/requirements.txt`，`pip install`
- [x] 1.2 在 `backend/.env.example` 中添加 `LANGCHAIN_TRACING_V2`、`LANGCHAIN_API_KEY`、`LANGCHAIN_PROJECT`、`LOG_LEVEL`、`PROMPT_LOG_MAX_LENGTH` 配置项及注释
- [x] 1.3 在 `backend/core/config.py` 的 `Settings` 类中添加对应字段及校验逻辑（`check_langsmith_config` validator：tracing 开启时 api_key 缺失仅 WARNING）

## 2. loguru 日志核心 (P0)

- [x] 2.1 创建 `backend/core/logging_config.py`：配置 loguru 双 sink（终端彩色 `sys.stderr` + NDJSON 文件 `logs/app_{time:YYYY-MM-DD}.ndjson`，rotation 每日，retention 7 天），实现 `InterceptHandler` 桥接标准 logging
- [x] 2.2 在 `backend/main.py` 的 app 创建后调用 `setup_logging()`，替换 uvicorn 默认 logging，启动时输出初始化日志
- [x] 2.3 在 `backend/core/logging_config.py` 中实现 `get_logger(name)` 工厂函数，返回绑定了模块名的 loguru logger

## 3. 请求中间件与错误分类 (P0)

- [x] 3.1 创建 `backend/core/middleware.py`：实现 `RequestLoggingMiddleware`（ASGI middleware），记录 method/path/status/duration_ms/corr_id，读取/生成 `X-Correlation-ID` 头
- [x] 3.2 在 `backend/main.py` 的 CORS middleware 之后注册 `RequestLoggingMiddleware`
- [x] 3.3 创建 `backend/core/error_classifier.py`：定义 `ErrorCategory` enum 和 `classify_error(exception) -> ErrorCategory` 函数，覆盖 OpenAI/Anthropic/DeepSeek 的 rate_limit/timeout/content_filter 异常类型

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
